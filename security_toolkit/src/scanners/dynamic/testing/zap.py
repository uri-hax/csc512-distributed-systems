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
    NormalizedSeverity,
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

# ZAP risk codes to normalized severity
_ZAP_RISK_MAP: dict[int, NormalizedSeverity] = {
    0: NormalizedSeverity.INFO,  # Informational
    1: NormalizedSeverity.LOW,  # Low
    2: NormalizedSeverity.MEDIUM,  # Medium
    3: NormalizedSeverity.HIGH,  # High
}

# ZAP confidence codes
_ZAP_CONFIDENCE: dict[int, str] = {
    0: "false-positive",
    1: "low",
    2: "medium",
    3: "high",
    4: "confirmed",
}


class ZAPScanner(ScannerPlugin):
    name: ClassVar[str] = "zap"
    scan_modes: ClassVar[set[str]] = {ScanMode.RUNTIME}

    # Check if this scanner can run for the given target
    def can_handle(self, profile: TargetProfile) -> bool:
        if profile.image is None and profile.service_url is None:
            return False
        if not docker_available():
            return False
        if not check_tool_available("zap-cli"):
            # ZAP CLI not installed -- check if we can use the Docker image
            if not self._zap_docker_available():
                logger.warning(
                    "Neither zap-cli nor ZAP Docker image available -- skipping ZAP scan"
                )
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
                    logger.warning("Service at %s not reachable for ZAP", base_url)
                    return []
                if check_tool_available("zap-cli"):
                    return self._run_zap_cli(base_url)
                # For Docker-based ZAP, replace localhost with host.docker.internal
                docker_url = base_url.replace(
                    "localhost", "host.docker.internal"
                ).replace("127.0.0.1", "host.docker.internal")
                from urllib.parse import urlparse
                port = urlparse(base_url).port or 80
                return self._run_zap_docker(docker_url, port)

            # Otherwise start a container from the image
            assert profile.image is not None
            container_name, host_port = self._start_service(
                profile.image, profile.exposed_ports
            )
            if not container_name or not host_port:
                return []

            base_url = f"http://host.docker.internal:{host_port}"
            localhost_url = f"http://localhost:{host_port}"

            if not self._wait_for_health(localhost_url, retries=10, delay=2):
                logger.warning(
                    "Service at %s did not become healthy for ZAP", localhost_url
                )
                return []

            # Try ZAP CLI first, then Docker image
            if check_tool_available("zap-cli"):
                return self._run_zap_cli(localhost_url)
            return self._run_zap_docker(base_url, host_port)

        except Exception:
            logger.exception("ZAP scan failed")
            return []
        finally:
            if container_name:
                stop_and_remove_container(container_name)
    # Service lifecycle
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

        container_name = f"sectoolkit_zap_{uuid.uuid4().hex[:8]}"
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error("Failed to start ZAP target: %s", result.stderr)
            return None, None

        # Discover the allocated host port
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
            logger.error("Could not determine host port for ZAP target")
            stop_and_remove_container(container_name)
            return None, None

        logger.info("ZAP target running: %s -> localhost:%d", container_name, host_port)
        return container_name, host_port

    @staticmethod
    def _wait_for_health(url: str, retries: int = 10, delay: int = 2) -> bool:
        import urllib.request
        import urllib.error

        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5):
                    logger.info("ZAP health check passed on attempt %d", attempt + 1)
                    return True
            except urllib.error.HTTPError:
                logger.info(
                    "ZAP health check passed on attempt %d (HTTP error)", attempt + 1
                )
                return True
            except Exception:
                time.sleep(delay)
        return False
    # ZAP Docker image runner
    @staticmethod
    def _zap_docker_available() -> bool:
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", "ghcr.io/zaproxy/zaproxy:stable"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True
            # Try to pull it
            logger.info("Pulling ZAP Docker image...")
            pull = subprocess.run(
                ["docker", "pull", "ghcr.io/zaproxy/zaproxy:stable"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return pull.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _run_zap_docker(target_url: str, host_port: int) -> list[Finding]:
        import uuid

        zap_container = f"sectoolkit_zap_runner_{uuid.uuid4().hex[:8]}"

        with tempfile.TemporaryDirectory(prefix="zap_") as tmpdir:
            report_path = Path(tmpdir) / "zap_report.json"
            report_path.touch()
            report_path.chmod(0o666)

            cmd = [
                "docker",
                "run",
                "--rm",
                "--name",
                zap_container,
                "--add-host",
                "host.docker.internal:host-gateway",
                "--cpus",
                "1",
                "--memory",
                "512m",
                "-v",
                f"{tmpdir}:/zap/wrk:rw",
                "-u",
                "zap",
                "ghcr.io/zaproxy/zaproxy:stable",
                "zap-baseline.py",
                "-t",
                target_url,
                "-J",
                "zap_report.json",
                "-I",  # Don't fail on warnings
                "-d",  # Show debug messages
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                # ZAP baseline exits with:
                # 0 = pass, 1 = at least one WARN, 2 = at least one FAIL
                if result.returncode not in (0, 1, 2):
                    logger.error(
                        "ZAP scan failed (exit %d): %s",
                        result.returncode,
                        result.stderr[:500],
                    )
                    return []
            except subprocess.TimeoutExpired:
                logger.error("ZAP scan timed out after 300s")
                # Clean up container
                subprocess.run(
                    ["docker", "rm", "-f", zap_container],
                    capture_output=True,
                    timeout=10,
                )
                return []
            except Exception:
                logger.exception("Failed to execute ZAP Docker scan")
                return []

            return ZAPScanner._parse_zap_json(report_path)
    # ZAP CLI runner
    @staticmethod
    def _run_zap_cli(target_url: str) -> list[Finding]:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="zap_"
        ) as f:
            output_file = f.name

        try:
            # Quick scan: spider + passive + active scan
            subprocess.run(
                [
                    "zap-cli",
                    "quick-scan",
                    "--self-contained",
                    "--start-options",
                    "-config api.disablekey=true",
                    "-o",
                    "-f",
                    "json",
                    target_url,
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except Exception:
            logger.exception("zap-cli execution failed")
            return []

        findings = ZAPScanner._parse_zap_json(Path(output_file))
        Path(output_file).unlink(missing_ok=True)
        return findings
    # Report parsing
    @staticmethod
    def _parse_zap_json(report_path: Path) -> list[Finding]:
        findings: list[Finding] = []

        try:
            content = report_path.read_text(encoding="utf-8").strip()
            if not content:
                logger.warning("ZAP report is empty")
                return []

            report = json.loads(content)
        except (json.JSONDecodeError, OSError):
            logger.exception("Failed to read/parse ZAP report")
            return []

        # ZAP JSON report structure:
        # { "site": [ { "alerts": [ { ... } ] } ] }
        sites = report.get("site", [])
        for site in sites:
            alerts = site.get("alerts", [])
            for alert in alerts:
                rule_id = alert.get("pluginid", alert.get("alertRef", "unknown"))
                risk_code = int(alert.get("riskcode", 0))
                confidence = int(alert.get("confidence", 1))
                name = alert.get("name", alert.get("alert", "ZAP finding"))
                desc = alert.get("desc", "")
                solution = alert.get("solution", "")
                reference = alert.get("reference", "")
                cwe_id = alert.get("cweid", "")
                wasc_id = alert.get("wascid", "")

                # Skip false positives
                if confidence == 0:
                    continue

                severity = _ZAP_RISK_MAP.get(risk_code, NormalizedSeverity.MEDIUM)
                confidence_label = _ZAP_CONFIDENCE.get(confidence, "unknown")

                # Build description
                full_desc = desc
                if solution:
                    full_desc += f"\n\nSolution: {solution}"
                if cwe_id and cwe_id != "-1":
                    full_desc += f"\nCWE: CWE-{cwe_id}"
                if wasc_id and wasc_id != "-1":
                    full_desc += f"\nWASC: WASC-{wasc_id}"

                # Get affected URLs
                instances = alert.get("instances", [])
                locations = []
                for inst in instances[:5]:  # Cap at 5 instances
                    uri = inst.get("uri", "")
                    method = inst.get("method", "")
                    if uri:
                        locations.append(f"{method} {uri}")

                location_str = ", ".join(locations) if locations else "target"

                findings.append(
                    Finding(
                        tool="zap",
                        rule_id=f"ZAP-{rule_id}",
                        title=f"{name} (confidence: {confidence_label})",
                        description=full_desc,
                        severity=severity,
                        file_path=location_str,
                        category="dast",
                        raw=alert,
                    )
                )

        return findings
