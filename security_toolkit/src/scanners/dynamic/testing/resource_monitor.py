"""Resource monitor plugin -- detects memory leaks and resource exhaustion.

Starts the target container, takes baseline resource measurements, triggers
operations that should cause resource growth (e.g., hitting a /leak endpoint),
and compares final measurements to detect abnormal resource consumption.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import time
import uuid
import urllib.error
import urllib.request
from typing import ClassVar

from security_toolkit.core.models import (
    Finding,
    NormalizedSeverity,
    ScanMode,
    TargetProfile,
)
from security_toolkit.core.plugin import ScannerPlugin
from security_toolkit.core.sandbox import stop_and_remove_container
from security_toolkit.utils.docker_utils import docker_available

logger = logging.getLogger(__name__)

_WEB_PORTS = {80, 443, 8080, 8443, 3000, 5000, 8000, 9000}

# Memory growth threshold (percentage) to flag as a leak
_MEMORY_GROWTH_THRESHOLD = 50  # 50% growth


def _parse_memory(mem_str: str) -> float:
    """Parse Docker stats memory string (e.g. '15.2MiB') to bytes."""
    mem_str = mem_str.strip()
    multipliers = {
        "B": 1,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
        "kB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
    }
    for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if mem_str.endswith(suffix):
            try:
                return float(mem_str[: -len(suffix)].strip()) * mult
            except ValueError:
                pass
    # Try raw number
    m = re.match(r"([\d.]+)", mem_str)
    return float(m.group(1)) if m else 0.0


class ResourceMonitor(ScannerPlugin):
    """Monitor container resource usage to detect leaks."""

    name: ClassVar[str] = "resource-monitor"
    scan_modes: ClassVar[set[str]] = {ScanMode.RUNTIME}

    def can_handle(self, profile: TargetProfile) -> bool:
        if profile.image is None and profile.service_url is None:
            return False
        if profile.image and not docker_available():
            return False
        if profile.service_url:
            return True
        if not profile.exposed_ports:
            return False
        return bool(set(profile.exposed_ports) & _WEB_PORTS)

    def execute(self, profile: TargetProfile) -> list[Finding]:
        assert profile.image is not None or profile.service_url is not None
        container_name: str | None = None

        try:
            # If a live service URL is provided with no image, run URL-only
            # resource checks (no docker stats available)
            if profile.service_url and profile.image is None:
                base_url = profile.service_url
                if not self._wait_for_health(base_url):
                    logger.warning("Service not reachable for resource monitoring")
                    return []
                return self._check_url_only_resources(
                    base_url, profile.service_url
                )

            # Standard container-based monitoring
            assert profile.image is not None
            container_name, host_port = self._start_service(
                profile.image, profile.exposed_ports
            )
            if not container_name or not host_port:
                return []

            base_url = f"http://localhost:{host_port}"
            if not self._wait_for_health(base_url):
                logger.warning("Service did not become healthy for resource monitoring")
                return []

            return self._monitor_resources(container_name, base_url, profile.image)

        except Exception:
            logger.exception("Resource monitoring failed")
            return []
        finally:
            if container_name:
                stop_and_remove_container(container_name)

    # ------------------------------------------------------------------

    @staticmethod
    def _start_service(
        image: str,
        exposed_ports: tuple[int, ...],
    ) -> tuple[str | None, int | None]:
        target_port = next(
            (p for p in exposed_ports if p in _WEB_PORTS),
            exposed_ports[0] if exposed_ports else None,
        )
        if target_port is None:
            return None, None

        container_name = f"sectoolkit_resmon_{uuid.uuid4().hex[:8]}"
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--cpus",
            "0.5",
            "--memory",
            "512m",
            "--pids-limit",
            "128",
            "--security-opt",
            "no-new-privileges",
            "-p",
            f"0:{target_port}",
            image,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error("Failed to start resource monitor target: %s", result.stderr)
            return None, None

        port_result = subprocess.run(
            ["docker", "port", container_name, str(target_port)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        port_line = (
            port_result.stdout.strip().split("\n")[0] if port_result.stdout else ""
        )
        if ":" in port_line:
            host_port = int(port_line.rsplit(":", 1)[-1])
        else:
            stop_and_remove_container(container_name)
            return None, None

        logger.info(
            "Resource monitor target: %s -> localhost:%d", container_name, host_port
        )
        return container_name, host_port

    @staticmethod
    def _wait_for_health(url: str, retries: int = 10, delay: int = 2) -> bool:
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5):
                    return True
            except urllib.error.HTTPError:
                # Any HTTP response (even 4xx/5xx) means the server is up
                return True
            except Exception:
                time.sleep(delay)
        return False

    @staticmethod
    def _get_container_memory(container_name: str) -> float:
        """Get current memory usage in bytes via docker stats."""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{.MemUsage}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Format: "15.2MiB / 512MiB" -- take the first part
                usage = result.stdout.strip().split("/")[0].strip()
                return _parse_memory(usage)
        except Exception:
            logger.debug("Failed to get container memory stats")
        return 0.0

    @staticmethod
    def _monitor_resources(
        container_name: str, base_url: str, image: str
    ) -> list[Finding]:
        """Measure resource usage before and after triggering leak endpoints."""
        findings: list[Finding] = []

        # Take baseline measurement
        time.sleep(2)
        initial_memory = ResourceMonitor._get_container_memory(container_name)
        logger.info(
            "Initial memory usage: %.2f bytes (%.2f MiB)",
            initial_memory,
            initial_memory / (1024**2),
        )

        if initial_memory == 0:
            logger.warning(
                "Could not measure initial memory, skipping resource monitoring"
            )
            return []

        # Trigger memory leak endpoints
        leak_url = f"{base_url}/leak"
        allocate_url = f"{base_url}/allocate?size=500000"
        leak_triggered = False

        for url in [leak_url, allocate_url]:
            for _ in range(5):
                try:
                    req = urllib.request.Request(url, method="GET")
                    with urllib.request.urlopen(req, timeout=10):
                        leak_triggered = True
                except Exception:
                    pass

        if not leak_triggered:
            logger.info("No leak/allocate endpoints found, skipping memory leak test")
            return []

        # Wait for memory to settle
        time.sleep(3)

        # Take final measurement
        final_memory = ResourceMonitor._get_container_memory(container_name)
        logger.info(
            "Final memory usage: %.2f bytes (%.2f MiB)",
            final_memory,
            final_memory / (1024**2),
        )

        if final_memory == 0:
            return []

        growth_pct = ((final_memory - initial_memory) / initial_memory) * 100

        if growth_pct > _MEMORY_GROWTH_THRESHOLD:
            findings.append(
                Finding(
                    tool="resource-monitor",
                    rule_id="RESLEAK-001",
                    title="Memory leak detected: significant memory growth",
                    description=(
                        f"Container memory grew from "
                        f"{initial_memory / (1024 ** 2):.1f} MiB to "
                        f"{final_memory / (1024 ** 2):.1f} MiB "
                        f"({growth_pct:.0f}% increase) after hitting "
                        f"/leak and /allocate endpoints. This indicates "
                        f"unbounded memory growth that could lead to OOM "
                        f"crashes in long-running deployments."
                    ),
                    severity=NormalizedSeverity.HIGH,
                    file_path=f"runtime://{image}",
                    category="resource-leak",
                    raw={
                        "initial_memory_bytes": initial_memory,
                        "final_memory_bytes": final_memory,
                        "growth_percentage": round(growth_pct, 1),
                        "threshold_percentage": _MEMORY_GROWTH_THRESHOLD,
                    },
                )
            )

        # Check for connection leaks
        conn_url = f"{base_url}/connection-leak"
        try:
            for _ in range(10):
                req = urllib.request.Request(conn_url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                    conn_count = data.get("connections", 0)

            if conn_count > 5:
                findings.append(
                    Finding(
                        tool="resource-monitor",
                        rule_id="RESLEAK-002",
                        title="Connection leak detected: unclosed connections accumulating",
                        description=(
                            f"After 10 requests to /connection-leak, "
                            f"{conn_count} connections remain unclosed. "
                            f"Connections are accumulated in a list without "
                            f"proper cleanup, which will eventually exhaust "
                            f"file descriptors or connection pool limits."
                        ),
                        severity=NormalizedSeverity.MEDIUM,
                        file_path=f"runtime://{image}/connection-leak",
                        category="resource-leak",
                        raw={"open_connections": conn_count},
                    )
                )
        except Exception:
            logger.debug("Connection leak endpoint not available")

        return findings

    @staticmethod
    def _check_url_only_resources(
        base_url: str, label: str
    ) -> list[Finding]:
        """Run resource checks against a live URL without Docker stats.

        When no Docker image is provided we cannot measure container memory,
        but we can still exercise leak/allocate/connection-leak endpoints
        and observe behaviour.
        """
        findings: list[Finding] = []

        # Test connection leaks
        conn_url = f"{base_url}/connection-leak"
        conn_count = 0
        try:
            for _ in range(10):
                req = urllib.request.Request(conn_url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                    conn_count = data.get("connections", 0)

            if conn_count > 5:
                findings.append(
                    Finding(
                        tool="resource-monitor",
                        rule_id="RESLEAK-002",
                        title="Connection leak detected: unclosed connections accumulating",
                        description=(
                            f"After 10 requests to /connection-leak, "
                            f"{conn_count} connections remain unclosed. "
                            f"Connections are accumulated without proper cleanup."
                        ),
                        severity=NormalizedSeverity.MEDIUM,
                        file_path=f"runtime://{label}/connection-leak",
                        category="resource-leak",
                        raw={"open_connections": conn_count},
                    )
                )
        except Exception:
            logger.debug("Connection leak endpoint not available")

        # Test unbounded allocation
        allocate_url = f"{base_url}/allocate?size=500000"
        alloc_ok = 0
        try:
            for _ in range(5):
                req = urllib.request.Request(allocate_url, method="GET")
                with urllib.request.urlopen(req, timeout=10):
                    alloc_ok += 1
            if alloc_ok >= 5:
                findings.append(
                    Finding(
                        tool="resource-monitor",
                        rule_id="RESLEAK-003",
                        title="Unbounded memory allocation accepted without limit",
                        description=(
                            f"The /allocate endpoint accepted {alloc_ok}/5 "
                            f"large allocation requests (500 KB each) without "
                            f"any rate limiting or size cap."
                        ),
                        severity=NormalizedSeverity.MEDIUM,
                        file_path=f"runtime://{label}/allocate",
                        category="resource-leak",
                        raw={"successful_allocations": alloc_ok},
                    )
                )
        except Exception:
            pass

        return findings
