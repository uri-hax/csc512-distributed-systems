"""Sandbox utilities for resource-limited and network-isolated execution.

* :func:`run_with_limits` -- execute a subprocess with CPU / memory caps.
* :func:`create_isolated_network` / :func:`remove_isolated_network` -- manage
  a dedicated Docker bridge network for runtime scans.
* :func:`run_container_sandboxed` -- start a container on the isolated
  network with strict resource constraints.
"""

from __future__ import annotations

import logging
import resource
import subprocess
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resource-limited subprocess execution
# ---------------------------------------------------------------------------

# Defaults: 5 minutes CPU, 2 GiB RSS
_DEFAULT_CPU_LIMIT_SECONDS = 300
_DEFAULT_MEM_LIMIT_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB


def _preexec_limits(
    cpu: int = _DEFAULT_CPU_LIMIT_SECONDS,
    mem: int = _DEFAULT_MEM_LIMIT_BYTES,
) -> None:
    """``preexec_fn`` callback that sets rlimits on the child process."""
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
    """Run *cmd* in a subprocess with CPU and memory rlimits.

    Returns the :class:`subprocess.CompletedProcess` on success.
    Raises :class:`subprocess.TimeoutExpired` or
    :class:`subprocess.CalledProcessError` on failure.
    """
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


# ---------------------------------------------------------------------------
# Docker network isolation
# ---------------------------------------------------------------------------

_NETWORK_PREFIX = "sectoolkit_isolated_"


@dataclass
class IsolatedNetwork:
    """Handle for a Docker network created by the toolkit."""

    name: str
    id: str


def create_isolated_network() -> IsolatedNetwork:
    """Create a Docker bridge network with ``--internal`` to prevent
    outbound internet access from containers attached to it."""
    name = f"{_NETWORK_PREFIX}{uuid.uuid4().hex[:8]}"
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
    """Remove a previously created Docker network."""
    subprocess.run(
        ["docker", "network", "rm", network.name],
        capture_output=True,
        text=True,
        timeout=30,
    )
    logger.info("Removed isolated network: %s", network.name)


# ---------------------------------------------------------------------------
# Sandboxed container execution
# ---------------------------------------------------------------------------


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
    """Start a container with strict sandboxing.

    Parameters:
        image:       Docker image to run.
        network:     Isolated network handle.
        command:     Override CMD.
        cpus:        CPU quota (e.g. ``"0.5"``).
        memory:      Memory limit (e.g. ``"256m"``).
        read_only:   Mount the root filesystem read-only.
        extra_args:  Additional ``docker run`` arguments.
        detach:      Run in detached mode and return the container ID.
        timeout:     Seconds before killing the container.

    Returns:
        A dict with ``container_id`` and optionally ``stdout``/``stderr``.
    """
    container_name = f"sectoolkit_{uuid.uuid4().hex[:8]}"
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
    container_id = result.stdout.strip().split("\n")[-1] if result.stdout else ""
    return {
        "container_id": container_id,
        "container_name": container_name,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def stop_and_remove_container(container: str) -> None:
    """Force-stop and remove a container by name or ID."""
    subprocess.run(
        ["docker", "rm", "-f", container],
        capture_output=True,
        text=True,
        timeout=30,
    )
    logger.debug("Removed container: %s", container)
