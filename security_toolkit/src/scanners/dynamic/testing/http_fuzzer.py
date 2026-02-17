# HTTP fuzzer (Nuclei): tests web apps for vulnerabilities
# Dependencies: nuclei CLI tool
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import ClassVar

from security_toolkit.core.models import (
    Finding,
    ScanMode,
    TargetProfile,
    normalize_severity,
)
from security_toolkit.core.plugin import ScannerPlugin
from security_toolkit.core.sandbox import stop_and_remove_container
from security_toolkit.utils.docker_utils import docker_available
from security_toolkit.utils.process_utils import check_tool_available

logger = logging.getLogger(__name__)

# Ports commonly used by web services
_WEB_PORTS = {80, 443, 8080, 8443, 3000, 5000, 8000, 9000}


class DASTScanner(ScannerPlugin):
    name: ClassVar[str] = "dast"
    scan_modes: ClassVar[set[str]] = {ScanMode.RUNTIME}

    # Check if this scanner can run for the given target
    def can_handle(self, profile: TargetProfile) -> bool:
        if profile.image is None and profile.service_url is None:
            return False
        if profile.image and not docker_available():
            return False
        if not check_tool_available("nuclei"):
            logger.warning("nuclei not found on PATH -- skipping DAST scan")
            return False
        # Only activate if the image exposes web-ish ports or a URL is given
        if profile.service_url:
            return True
        if not profile.exposed_ports:
            return False
        return bool(set(profile.exposed_ports) & _WEB_PORTS)

    # Run the scan and return findings
    def execute(self, profile: TargetProfile) -> list[Finding]:
        assert profile.image is not None or profile.service_url is not None
        container_name: str | None = None

        try:
            # If a live service URL is provided, use it directly
            if profile.service_url:
                base_url = profile.service_url
                if not self._wait_for_health(base_url, retries=3, delay=1):
                    logger.warning("Service at %s not reachable", base_url)
                    return []
                return self._run_nuclei(base_url)

            # Otherwise start a container from the image
            assert profile.image is not None
            container_name, host_port = self._start_service(
                profile.image, profile.exposed_ports
            )
            if not container_name or not host_port:
                return []

            base_url = f"http://localhost:{host_port}"
            if not self._wait_for_health(base_url, retries=10, delay=2):
                logger.warning("Service at %s did not become healthy", base_url)
                return []

            return self._run_nuclei(base_url)

        except Exception:
            logger.exception("DAST scan failed")
            return []
        finally:
            if container_name:
                stop_and_remove_container(container_name)
    # Helpers
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

        import uuid

        container_name = f"sectoolkit_dast_{uuid.uuid4().hex[:8]}"
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--cpus",
            "0.5",
            "--memory",
            "256m",
            "--pids-limit",
            "128",
            "--security-opt",
            "no-new-privileges",
            "-p",
            f"0:{target_port}",
            image,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error("Failed to start DAST target: %s", result.stderr)
            return None, None

        # Discover the allocated host port
        port_result = subprocess.run(
            [
                "docker",
                "port",
                container_name,
                str(target_port),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Output format: "0.0.0.0:32768" or "[::]:32768"
        port_line = (
            port_result.stdout.strip().split("\n")[0] if port_result.stdout else ""
        )
        if ":" in port_line:
            host_port = int(port_line.rsplit(":", 1)[-1])
        else:
            logger.error("Could not determine host port for DAST target")
            stop_and_remove_container(container_name)
            return None, None

        logger.info(
            "DAST target running: %s -> localhost:%d", container_name, host_port
        )
        return container_name, host_port

    @staticmethod
    def _wait_for_health(url: str, retries: int = 10, delay: int = 2) -> bool:
        import urllib.request
        import urllib.error

        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5):
                    logger.info("Health check passed on attempt %d", attempt + 1)
                    return True
            except urllib.error.HTTPError:
                # Any HTTP response (even 4xx/5xx) means the server is up
                logger.info("Health check passed on attempt %d (HTTP error response)", attempt + 1)
                return True
            except Exception:
                time.sleep(delay)
        return False
    # Nuclei
    @staticmethod
    def _run_nuclei(base_url: str) -> list[Finding]:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="nuclei_"
        ) as f:
            output_file = f.name

        cmd = [
            "nuclei",
            "-u",
            base_url,
            "-jsonl",
            "-o",
            output_file,
            "-severity",
            "info,low,medium,high,critical",
            "-silent",
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except Exception:
            logger.exception("Nuclei execution failed")
            return []

        findings: list[Finding] = []
        try:
            content = Path(output_file).read_text(encoding="utf-8")
            for line in content.strip().split("\n"):
                if not line:
                    continue
                entry = json.loads(line)
                info = entry.get("info", {})
                findings.append(
                    Finding(
                        tool="nuclei",
                        rule_id=entry.get("template-id", "unknown"),
                        title=info.get("name", "Nuclei finding"),
                        description=info.get("description", ""),
                        severity=normalize_severity(info.get("severity", "info")),
                        file_path=entry.get("matched-at", base_url),
                        category="dast",
                        raw=entry,
                    )
                )
        except Exception:
            logger.exception("Failed to parse Nuclei output")
        finally:
            Path(output_file).unlink(missing_ok=True)

        return findings
