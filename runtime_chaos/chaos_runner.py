# Mirrored after docker_runner.py but reworked for Chaos
# Key difference from run_in_container():
#   - Accepts a chaos profile name
#   - Starts a background thread that calls `docker update` and `docker exec tc (traffic control)`
#     at scheduled times while the container runs
#   - Returns a ChaosRunResult instead of a bare (returncode, stdout, stderr) tuple

import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field

from chaos_config import ChaosProfile, ResourceSnapshot, get_profile

DOCKER_IMAGES = {
    "python": "submission-runner-python",
    "c":      "submission-runner-c",
    "cpp":    "submission-runner-cpp",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ChaosEvent:
    elapsed_s: float
    message: str
    level: str = "info"

    def __str__(self) -> str:
        icon = {"info": "·", "warn": "⚠", "error": "✖"}.get(self.level, "·")
        return f"[{self.elapsed_s:6.1f}s] {icon}  {self.message}"


@dataclass
class ChaosRunResult:
    returncode: int
    stdout: str
    stderr: str
    profile_name: str
    events: list[ChaosEvent] = field(default_factory=list)
    oom_killed: bool = False
    timed_out: bool = False
    wall_time_s: float = 0.0

    # ── Compatibility shim ────────────────────────────────────────────────────
    def as_tuple(self):
        """Return (returncode, stdout, stderr) to match run_in_container() callers."""
        return self.returncode, self.stdout, self.stderr

    def print_report(self):
        """Pretty-print the full chaos run report."""
        bar = "═" * 56
        print(f"\n{bar}")
        print(f"  CHAOS RUN REPORT — profile: {self.profile_name!r}")
        print(bar)
        print(f"  Exit code  : {self.returncode}")
        print(f"  Wall time  : {self.wall_time_s:.2f}s")
        print(f"  OOM killed : {self.oom_killed}")
        print(f"  Timed out  : {self.timed_out}")
        print(f"\n  Timeline:")
        for e in self.events:
            print(f"    {e}")
        if self.stdout:
            print(f"\n  stdout (last 2000 chars):\n{self.stdout[-2000:]}")
        if self.stderr:
            print(f"\n  stderr:\n{self.stderr[:500]}")
        print(bar)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def run_in_container_with_chaos(
    language: str,
    command: list[str],
    submission_dir: str,
    profile_name: str = "none",
    timeout: int = 30,
) -> ChaosRunResult:
    """
    Chaos-aware replacement for run_in_container().

    Args:
        language:       "python", "c", or "cpp"  (same as run_in_container)
        command:        Command list              (same as run_in_container)
        submission_dir: Host path to submission   (same as run_in_container)
        profile_name:   Chaos profile to apply   (new)
        timeout:        Max seconds              (same as run_in_container)

    Returns:
        ChaosRunResult — call .as_tuple() if you need the old (rc, out, err) shape.

    Example:
        result = run_in_container_with_chaos(
            "c", ["./long_runner"], "/path/to/submission",
            profile_name="cpu_gradual", timeout=90
        )
        result.print_report()
        rc, out, err = result.as_tuple()
    """
    image = DOCKER_IMAGES.get(language)
    if not image:
        raise ValueError(f"Unsupported language: {language!r}. "
                         f"Known: {list(DOCKER_IMAGES)}")

    profile = get_profile(profile_name)
    return _run(image, command, submission_dir, profile, timeout)


# ═══════════════════════════════════════════════════════════════════════════════
# Core runner
# ═══════════════════════════════════════════════════════════════════════════════

def _run(
    image: str,
    command: list[str],
    submission_dir: str,
    profile: ChaosProfile,
    timeout: int,
) -> ChaosRunResult:
    import os
    submission_dir = os.path.abspath(submission_dir)

    events: list[ChaosEvent] = []
    container_name = f"grader-chaos-{uuid.uuid4().hex[:10]}"
    start = time.monotonic()

    def log(msg: str, level: str = "info"):
        events.append(ChaosEvent(round(time.monotonic() - start, 2), msg, level))

    # ── Build docker run command ──────────────────────────────────────────────
    docker_cmd = [
        "docker", "run",
        "--name",    container_name,
        "--rm",
        "-v",        f"{submission_dir}:/submission",
        "-w",        "/submission",
        "--user",    "1000:1000",
        "--pids-limit", "64",                 # block fork bombs
        "--security-opt", "no-new-privileges",
    ]

    # Network: profiles with net chaos need a real network namespace + NET_ADMIN.
    # Everything else keeps your existing "--network none".
    if profile.needs_net_admin:
        docker_cmd += ["--network", "bridge", "--cap-add", "NET_ADMIN"]
        log("Network chaos enabled — container has bridge network + NET_ADMIN")
    else:
        docker_cmd += ["--network", "none"]

    # Apply initial resource constraints from the profile
    docker_cmd += profile.initial.to_run_flags()

    # If the profile sets no initial limits, fall back to your existing defaults
    if profile.initial.cpu_quota is None:
        docker_cmd += ["--cpus", "1.0"]
    if profile.initial.memory_mb is None:
        docker_cmd += ["--memory", "512m"]

    docker_cmd += [image, *command]

    log(f"Container: {container_name}")
    log(f"Profile  : {profile.name} — {profile.description}")
    log(f"Command  : {' '.join(command)}")

    # ── Start background chaos injection thread ───────────────────────────────
    stop_event = threading.Event()
    chaos_thread = threading.Thread(
        target=_chaos_worker,
        args=(container_name, profile, start, events, stop_event),
        daemon=True,
    )

    # ── Launch container ──────────────────────────────────────────────────────
    oom_killed = False
    timed_out  = False

    try:
        chaos_thread.start()

        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        returncode = result.returncode
        stdout     = result.stdout
        stderr     = result.stderr

        if returncode == 137:
            oom_killed = True
            log("OOM killed (exit 137)", "warn")
        elif returncode != 0:
            log(f"Non-zero exit: {returncode}", "warn")

    except subprocess.TimeoutExpired:
        timed_out = True
        log(f"Timeout after {timeout}s — killing container", "warn")
        subprocess.run(["docker", "kill", container_name],
                       capture_output=True, timeout=5)
        returncode = -1
        stdout     = ""
        stderr     = f"Timed out after {timeout}s"

    except Exception as exc:
        log(f"Unexpected runner error: {exc}", "error")
        returncode = -2
        stdout     = ""
        stderr     = str(exc)

    finally:
        stop_event.set()

    return ChaosRunResult(
        returncode   = returncode,
        stdout       = stdout,
        stderr       = stderr,
        profile_name = profile.name,
        events       = events,
        oom_killed   = oom_killed,
        timed_out    = timed_out,
        wall_time_s  = round(time.monotonic() - start, 2),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Background chaos worker
# ═══════════════════════════════════════════════════════════════════════════════

def _chaos_worker(
    container_name: str,
    profile: ChaosProfile,
    start: float,
    events: list[ChaosEvent],
    stop: threading.Event,
):
    """
    Runs in a daemon thread alongside the container.
    Wakes up at each DynamicStep's scheduled time and applies the new constraints.
    """
    def log(msg: str, level: str = "info"):
        events.append(ChaosEvent(round(time.monotonic() - start, 2), msg, level))

    # Apply initial network rules once the container is up (~1-2s after launch)
    if profile.initial.has_net_chaos():
        if not stop.wait(timeout=2.5):   # wait for container init
            _apply_net(container_name, profile.initial, log)

    # Walk through dynamic steps in time order
    for step in sorted(profile.steps, key=lambda s: s.delay_s):
        # Sleep until this step is due
        remaining = step.delay_s - (time.monotonic() - start)
        if remaining > 0:
            if stop.wait(timeout=remaining):
                return  # container finished early
        if stop.is_set():
            return

        label = step.label or f"step@{step.delay_s}s"
        log(f"Applying: {label}")

        # 1. CPU / memory / blkio via docker update
        _apply_update(container_name, step.snapshot, log)

        # 2. Network via tc inside container
        if profile.needs_net_admin:
            _apply_net(container_name, step.snapshot, log)


def _apply_update(
    container_name: str,
    snap: ResourceSnapshot,
    log,
):
    """Call `docker update` to change CPU/memory/blkio on the running container."""
    flags = snap.to_update_flags()
    if not flags:
        return

    cmd = ["docker", "update"] + flags + [container_name]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    if r.returncode != 0:
        log(f"docker update failed: {r.stderr.strip()}", "warn")
    else:
        log(f"docker update: {' '.join(flags)}")


def _apply_net(
    container_name: str,
    snap: ResourceSnapshot,
    log,
):
    """Run tc commands inside the container via docker exec."""
    for tc_cmd in snap.to_tc_commands():
        full = ["docker", "exec", container_name] + tc_cmd
        r = subprocess.run(full, capture_output=True, text=True, timeout=5)
        # tc del on a clean interface returns an error — suppress it
        if r.returncode != 0 and "RTNETLINK" not in r.stderr:
            log(f"tc warn: {r.stderr.strip()}", "warn")