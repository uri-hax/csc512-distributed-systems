from pathlib import Path
import os
import subprocess
import threading
import time
import uuid
import re
import sys
from dataclasses import dataclass, field

from chaos_config import ChaosProfile, ResourceSnapshot, get_profile
from submission_runner.docker_runner import DOCKER_IMAGES


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
    log_dir: str | None = None
    peak_rss_mb:  float = 0.0
    cpu_peak_pct: float = 0.0
    cpu_avg_pct:  float = 0.0
    pids_peak:    int   = 0

    def as_tuple(self):
        """Return (returncode, stdout, stderr) to match run_in_container() callers."""
        return self.returncode, self.stdout, self.stderr

    def print_student_report(self):
        from report_format import parse_metrics, generate_feedback
        metrics = parse_metrics(self.stdout)
        feedback = generate_feedback(metrics, self)

        if self.log_dir:
            print("\n════════ STUDENT SUMMARY ════════")
            for line in feedback:
                print(line)
            print("\n Key Metrics:")
            print(f"CPU avg ops/sec: {metrics['cpu_avg']:.0f}")
            print(f"CPU min ops/sec: {metrics['cpu_min']:.0f}")
            print(f"Memory peak: {metrics['mem_peak']} MB")
            print("\n Full logs available in saved report folder")

    def print_report(self):
        bar = "═" * 56
        print(f"\n{bar}")
        print(f"  CHAOS RUN REPORT profile: {self.profile_name!r}")
        print(bar)
        print(f"  Exit code  : {self.returncode}")
        print(f"  Wall time  : {self.wall_time_s:.2f}s")
        print(f"  OOM killed : {self.oom_killed}")
        print(f"  Timed out  : {self.timed_out}")
        print(f"\n  Timeline:")
        for e in self.events:
            print(f"    {e}")
        if self.log_dir:
            print(f"\n Raw logs saved to: {self.log_dir}")
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
        "--pids-limit", "64",
        "--security-opt", "no-new-privileges",
    ]

    if profile.needs_net_admin:
        docker_cmd += ["--network", "bridge", "--cap-add", "NET_ADMIN"]
        log("Network chaos enabled — container has bridge network + NET_ADMIN")
    else:
        docker_cmd += ["--network", "none"]

    docker_cmd += profile.initial.to_run_flags()

    if profile.initial.cpu_quota is None:
        docker_cmd += ["--cpus", "1.0"]
    if profile.initial.memory_mb is None:
        docker_cmd += ["--memory", "512m"]

    docker_cmd += [image, *command]

    log(f"Container: {container_name}")
    log(f"Profile  : {profile.name} — {profile.description}")
    log(f"Command  : {' '.join(command)}")

    # ── Shared stats dict populated by _chaos_worker ────────────────────────
    docker_stats: dict = {}

    stop_event = threading.Event()
    chaos_thread = threading.Thread(
        target=_chaos_worker,
        args=(container_name, profile, start, events, stop_event, docker_stats),
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
        print(f"DEBUG returncode={returncode}", file=sys.stderr)

    except subprocess.TimeoutExpired:
        timed_out = True
        log(f"Timeout after {timeout}s: killing container", "warn")
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
        chaos_thread.join(timeout=6)   # wait for stats to flush into docker_stats

    events_clean = [e for e in events
                    if not (e.elapsed_s == -1 and e.level == "stats")]

    return ChaosRunResult(
        returncode   = returncode,
        stdout       = stdout,
        stderr       = stderr,
        profile_name = profile.name,
        events       = events_clean,
        oom_killed   = oom_killed,
        timed_out    = timed_out,
        wall_time_s  = round(time.monotonic() - start, 2),
        peak_rss_mb  = round(docker_stats.get("peak_rss_mb", 0.0), 1),
        cpu_peak_pct = round(docker_stats.get("cpu_peak", 0.0), 1),
        cpu_avg_pct  = round(docker_stats.get("cpu_avg", 0.0), 1),
        pids_peak    = docker_stats.get("pids_peak", 0),
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
    docker_stats: dict,           # shared dict written here, read by _run()
):
    def log(msg, level="info"):
        events.append(ChaosEvent(round(time.monotonic() - start, 2), msg, level))

    # ── Stats — written by poll_stats, flushed into docker_stats on exit ──────
    stats = {
        "peak_rss_mb":  0.0,
        "cpu_peak":     0.0,
        "cpu_samples":  [],
        "mem_samples":  [],
        "pids_peak":    0,
        "pids_samples": [],
    }

    def poll_stats():
        time.sleep(0.5)
        while not stop.is_set():
            try:
                r = subprocess.run(
                    ["docker", "stats", "--no-stream", "--format",
                     "{{.CPUPerc}}\t{{.MemUsage}}\t{{.PIDs}}",
                     container_name],
                    capture_output=True, text=True, timeout=3,
                )

                if r.returncode == 0 and r.stdout.strip():
                    parts = r.stdout.strip().split("\t")
                    if len(parts) == 3:
                        cpu_str, mem_str, pids_str = parts

                        m = re.search(r"([\d.]+)%", cpu_str)
                        if m:
                            sample = float(m.group(1))
                            stats["cpu_samples"].append(sample)
                            stats["cpu_peak"] = max(stats["cpu_peak"], sample)

                        m = re.match(r"([\d.]+)([KMG])iB", mem_str.strip())
                        if m:
                            val, unit = float(m.group(1)), m.group(2)
                            mb = (val if unit == "M" else
                                val / 1024 if unit == "K" else val * 1024)
                        elif mem_str.strip() == "0B / 0B":
                            mb = 0.0
                        else:
                            mb = None

                        if mb is not None and mb > 0:
                            stats["mem_samples"].append(mb)
                            stats["peak_rss_mb"] = max(stats["peak_rss_mb"], mb)

                        try:
                            pid_count = int(pids_str.strip())
                            stats["pids_samples"].append(pid_count)
                            stats["pids_peak"] = max(stats["pids_peak"], pid_count)
                        except ValueError:
                            pass

            except Exception:
                pass
            stop.wait(timeout=0.5)

    # ── Start stats polling thread ────────────────────────────────────────────
    stats_thread = threading.Thread(target=poll_stats, daemon=True)
    stats_thread.start()

    # ── Initial network rules ─────────────────────────────────────────────────
    if profile.initial.has_net_chaos():
        if not stop.wait(timeout=2.5):
            _apply_net(container_name, profile.initial, log)

    # ── Dynamic steps ─────────────────────────────────────────────────────────
    for step in sorted(profile.steps, key=lambda s: s.delay_s):
        remaining = step.delay_s - (time.monotonic() - start)
        if remaining > 0:
            if stop.wait(timeout=remaining):
                break
        if stop.is_set():
            break

        label = step.label or f"step@{step.delay_s}s"
        log(f"Applying: {label}")
        _apply_update(container_name, step.snapshot, log)
        if profile.needs_net_admin:
            _apply_net(container_name, step.snapshot, log)

    # ── Flush stats into shared dict ──────────────────────────────────────────
    stop.wait()

    stats["cpu_avg"] = (sum(stats["cpu_samples"]) / len(stats["cpu_samples"])
                        if stats["cpu_samples"] else 0.0)
    stats["mem_avg"] = (sum(stats["mem_samples"]) / len(stats["mem_samples"])
                        if stats["mem_samples"] else 0.0)
    del stats["cpu_samples"]
    del stats["mem_samples"]
    del stats["pids_samples"]

    docker_stats.update(stats)   # write into the shared dict _run() holds


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_update(
    container_name: str,
    snap: ResourceSnapshot,
    log,
):
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
        if r.returncode != 0 and "RTNETLINK" not in r.stderr:
            log(f"tc warn: {r.stderr.strip()}", "warn")