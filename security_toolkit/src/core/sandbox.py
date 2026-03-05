# Sandbox utilities: run subprocesses and containers with resource limits and network isolation
# Dependencies: resource (rlimits), subprocess (Docker commands), uuid (unique names)
from __future__ import annotations

import logging
import resource
import subprocess
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Defaults: 5 minutes CPU, 2 GiB RSS
_DEFAULT_CPU_LIMIT_SECONDS = 300
_DEFAULT_MEM_LIMIT_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB


# Called in child process before exec to set resource limits
def _preexec_limits(
    cpu: int = _DEFAULT_CPU_LIMIT_SECONDS,
    mem: int = _DEFAULT_MEM_LIMIT_BYTES,
) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    except ValueError:
        # macOS does not support RLIMIT_AS; fall back to RLIMIT_RSS
        try:
            resource.setrlimit(resource.RLIMIT_RSS, (mem, mem))
        except ValueError:
            logger.debug("Platform does not support RLIMIT_RSS either")


def run_with_limits(
    cmd: list[str],
    *,
    timeout: int = 600,
    cpu_limit: int = _DEFAULT_CPU_LIMIT_SECONDS,
    mem_limit: int = _DEFAULT_MEM_LIMIT_BYTES,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    logger.debug("Running (limited): %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
        env=env,
        preexec_fn=lambda: _preexec_limits(cpu_limit, mem_limit),
    )


_NETWORK_PREFIX = "sectoolkit_isolated_"


@dataclass
class IsolatedNetwork:
    name: str
    id: str


def create_isolated_network() -> IsolatedNetwork:
    name = f"{_NETWORK_PREFIX}{uuid.uuid4().hex[:8]}"
    # --internal flag prevents outbound internet access from containers on this network
    result = subprocess.run(
        ["docker", "network", "create", "--internal", "--driver", "bridge", name],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create Docker network: {result.stderr.strip()}")
    net_id = result.stdout.strip()
    logger.info("Created isolated network: %s (%s)", name, net_id[:12])
    return IsolatedNetwork(name=name, id=net_id)


def remove_isolated_network(network: IsolatedNetwork) -> None:
    subprocess.run(
        ["docker", "network", "rm", network.name],
        capture_output=True,
        text=True,
        timeout=30,
    )
    logger.info("Removed isolated network: %s", network.name)


def run_container_sandboxed(
    image: str,
    network: IsolatedNetwork,
    *,
    command: list[str] | None = None,
    cpus: str = "1.0",
    memory: str = "512m",
    read_only: bool = True,
    extra_args: list[str] | None = None,
    detach: bool = False,
    timeout: int = 120,
) -> dict[str, Any]:
    container_name = f"sectoolkit_{uuid.uuid4().hex[:8]}"
    # Security hardening: drop all capabilities, prevent privilege escalation, limit processes
    cmd = [
        "docker",
        "run",
        "--name",
        container_name,
        "--network",
        network.name,
        "--cpus",
        cpus,
        "--memory",
        memory,
        "--pids-limit",
        "256",
        "--security-opt",
        "no-new-privileges",
        "--cap-drop",
        "ALL",
    ]
    if read_only:
        cmd += ["--read-only"]
    if detach:
        cmd.append("-d")
    else:
        cmd.append("--rm")
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(image)
    if command:
        cmd.extend(command)

    logger.debug("Starting sandboxed container: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    # Extract container ID from last line of output (handles both detached and non-detached modes)
    container_id = result.stdout.strip().split("\n")[-1] if result.stdout else ""
    return {
        "container_id": container_id,
        "container_name": container_name,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def stop_and_remove_container(container: str) -> None:
    subprocess.run(
        ["docker", "rm", "-f", container],
        capture_output=True,
        text=True,
        timeout=30,
    )
    logger.debug("Removed container: %s", container)
