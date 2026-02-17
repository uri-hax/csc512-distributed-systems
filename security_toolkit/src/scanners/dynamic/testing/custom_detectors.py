# Custom security detectors: application-specific checks
# Dependencies: none (pure Python)
from __future__ import annotations

import json
import logging
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

# Patterns indicating secrets in HTTP responses
_SECRET_INDICATORS = [
    "password",
    "passwd",
    "secret",
    "api_key",
    "api_token",
    "access_key",
    "private_key",
    "aws_secret",
    "aws_access",
    "bearer ",
    "authorization",
]

# Endpoints commonly used to expose sensitive data
_SENSITIVE_ENDPOINTS = [
    "/info",
    "/env",
    "/config",
    "/debug",
    "/process-info",
    "/admin",
    "/status",
    "/metrics",
    "/actuator",
    "/actuator/env",
    "/.env",
    "/db-connect",
]


class CustomDetectors(ScannerPlugin):
    name: ClassVar[str] = "custom-detectors"
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

    # Run the scan and return findings
    def execute(self, profile: TargetProfile) -> list[Finding]:
        assert profile.image is not None or profile.service_url is not None
        container_name: str | None = None

        try:
            # If a live service URL is provided, use it directly
            if profile.service_url:
                base_url = profile.service_url
                if not self._wait_for_health(base_url):
                    logger.warning("Service not reachable for custom detection")
                    return []
                image_label = profile.image or profile.service_url
                findings: list[Finding] = []
                findings.extend(self._check_debug_mode(base_url, image_label))
                findings.extend(self._check_secret_endpoints(base_url, image_label))
                findings.extend(self._check_verbose_errors(base_url, image_label))
                findings.extend(self._check_timing_attack(base_url, image_label))
                findings.extend(self._check_auth_bypass(base_url, image_label))
                return findings

            # Otherwise start a container from the image
            assert profile.image is not None
            container_name, host_port = self._start_service(
                profile.image, profile.exposed_ports
            )
            if not container_name or not host_port:
                return []

            base_url = f"http://localhost:{host_port}"
            if not self._wait_for_health(base_url):
                logger.warning("Service did not become healthy for custom detection")
                return []

            findings: list[Finding] = []
            findings.extend(self._check_debug_mode(base_url, profile.image))
            findings.extend(self._check_secret_endpoints(base_url, profile.image))
            findings.extend(self._check_verbose_errors(base_url, profile.image))
            findings.extend(self._check_timing_attack(base_url, profile.image))
            findings.extend(self._check_auth_bypass(base_url, profile.image))
            return findings

        except Exception:
            logger.exception("Custom detection failed")
            return []
        finally:
            if container_name:
                stop_and_remove_container(container_name)
    # Service management
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

        container_name = f"sectoolkit_custom_{uuid.uuid4().hex[:8]}"
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
            logger.error("Failed to start custom detector target: %s", result.stderr)
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
            "Custom detector target: %s -> localhost:%d", container_name, host_port
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
    # Detection checks
    @staticmethod
    def _check_debug_mode(base_url: str, image: str) -> list[Finding]:
        findings: list[Finding] = []

        # Check for Werkzeug debugger
        debug_endpoints = ["/console", "/?__debugger__=yes"]
        for endpoint in debug_endpoints:
            try:
                url = f"{base_url}{endpoint}"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body = resp.read().decode(errors="replace").lower()
                    if any(
                        indicator in body
                        for indicator in [
                            "debugger",
                            "werkzeug",
                            "interactive",
                            "traceback",
                            "console",
                        ]
                    ):
                        findings.append(
                            Finding(
                                tool="custom-detectors",
                                rule_id="CUSTOM-DEBUG-001",
                                title="Debug mode enabled: interactive debugger accessible",
                                description=(
                                    f"The application at {url} exposes an interactive "
                                    f"debugger (Werkzeug/Flask debug mode). This allows "
                                    f"arbitrary code execution and must never be enabled "
                                    f"in non-development environments."
                                ),
                                severity=NormalizedSeverity.CRITICAL,
                                file_path=f"runtime://{image}",
                                category="custom",
                            )
                        )
                        break
            except urllib.error.HTTPError as e:
                # A 400/500 with debugger info is still a finding
                try:
                    body = e.read().decode(errors="replace").lower()
                    if "debugger" in body or "werkzeug" in body:
                        findings.append(
                            Finding(
                                tool="custom-detectors",
                                rule_id="CUSTOM-DEBUG-001",
                                title="Debug mode enabled: interactive debugger accessible",
                                description=(
                                    f"The application exposes debug information at "
                                    f"{base_url}{endpoint}. Debug mode must be disabled "
                                    f"in non-development environments."
                                ),
                                severity=NormalizedSeverity.CRITICAL,
                                file_path=f"runtime://{image}",
                                category="custom",
                            )
                        )
                        break
                except Exception:
                    pass
            except Exception:
                pass

        # Check response headers for debug indicators
        try:
            req = urllib.request.Request(base_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                server = resp.headers.get("Server", "").lower()
                if "werkzeug" in server or "development" in server:
                    findings.append(
                        Finding(
                            tool="custom-detectors",
                            rule_id="CUSTOM-DEBUG-002",
                            title="Development server detected in production",
                            description=(
                                f"The Server header indicates a development server "
                                f"({resp.headers.get('Server', '')}). Development "
                                f"servers lack the performance and security features "
                                f"of production-ready servers."
                            ),
                            severity=NormalizedSeverity.HIGH,
                            file_path=f"runtime://{image}",
                            category="custom",
                        )
                    )
        except Exception:
            pass

        return findings

    @staticmethod
    def _check_secret_endpoints(base_url: str, image: str) -> list[Finding]:
        findings: list[Finding] = []

        for endpoint in _SENSITIVE_ENDPOINTS:
            try:
                url = f"{base_url}{endpoint}"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body = resp.read().decode(errors="replace").lower()
                    exposed_secrets = [ind for ind in _SECRET_INDICATORS if ind in body]
                    if len(exposed_secrets) >= 2:
                        findings.append(
                            Finding(
                                tool="custom-detectors",
                                rule_id="CUSTOM-SECRETS-001",
                                title=f"Sensitive data exposed at {endpoint}",
                                description=(
                                    f"The endpoint {url} exposes sensitive information "
                                    f"including: {', '.join(exposed_secrets)}. "
                                    f"This endpoint should be removed or protected "
                                    f"with authentication."
                                ),
                                severity=NormalizedSeverity.CRITICAL,
                                file_path=f"runtime://{image}{endpoint}",
                                category="custom",
                                raw={"exposed_indicators": exposed_secrets},
                            )
                        )
            except Exception:
                pass

        return findings

    @staticmethod
    def _check_verbose_errors(base_url: str, image: str) -> list[Finding]:
        findings: list[Finding] = []

        # Trigger errors by sending bad input
        error_triggers = [
            f"{base_url}/compute?n=abc",  # Type error
            f"{base_url}/allocate?size=abc",  # Type error
            f"{base_url}/nonexistent-endpoint",  # 404
        ]

        for url in error_triggers:
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body = resp.read().decode(errors="replace")
                    if _has_stack_trace(body):
                        findings.append(
                            Finding(
                                tool="custom-detectors",
                                rule_id="CUSTOM-VERBOSE-001",
                                title="Verbose error messages with stack trace",
                                description=(
                                    f"The endpoint {url} returns detailed stack traces "
                                    f"in error responses. This leaks internal "
                                    f"implementation details (file paths, frameworks, "
                                    f"library versions) to attackers."
                                ),
                                severity=NormalizedSeverity.MEDIUM,
                                file_path=f"runtime://{image}",
                                category="custom",
                            )
                        )
                        break
            except urllib.error.HTTPError as e:
                try:
                    body = e.read().decode(errors="replace")
                    if _has_stack_trace(body):
                        findings.append(
                            Finding(
                                tool="custom-detectors",
                                rule_id="CUSTOM-VERBOSE-001",
                                title="Verbose error messages with stack trace",
                                description=(
                                    f"An error response from {url} contains detailed "
                                    f"stack traces. This leaks internal implementation "
                                    f"details to attackers."
                                ),
                                severity=NormalizedSeverity.MEDIUM,
                                file_path=f"runtime://{image}",
                                category="custom",
                            )
                        )
                        break
                except Exception:
                    pass
            except Exception:
                pass

        return findings

    @staticmethod
    def _check_timing_attack(base_url: str, image: str) -> list[Finding]:
        findings: list[Finding] = []
        auth_url = f"{base_url}/sensitive-operation"

        # Verify endpoint exists
        try:
            req = urllib.request.Request(f"{auth_url}?pwd=test", method="GET")
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError:
            pass  # Expected 401
        except Exception:
            return findings  # Endpoint doesn't exist

        # Measure response times for different password lengths
        timings: list[tuple[int, float]] = []
        for length in [1, 5, 10, 20, 30]:
            pwd = "a" * length
            start = time.monotonic()
            try:
                req = urllib.request.Request(f"{auth_url}?pwd={pwd}", method="GET")
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass
            elapsed = time.monotonic() - start
            timings.append((length, elapsed))

        # Check if response time correlates with password length
        if len(timings) >= 3:
            # Simple linear check: times should increase with length
            times = [t for _, t in timings]
            lengths = [l for l, _ in timings]
            if times[-1] > times[0] * 1.5 and lengths[-1] > lengths[0]:
                findings.append(
                    Finding(
                        tool="custom-detectors",
                        rule_id="CUSTOM-TIMING-001",
                        title="Timing attack vulnerability in authentication",
                        description=(
                            f"The /sensitive-operation endpoint shows timing "
                            f"correlation with input length. Response times ranged "
                            f"from {times[0]:.3f}s (length={lengths[0]}) to "
                            f"{times[-1]:.3f}s (length={lengths[-1]}). "
                            f"Use constant-time comparison for authentication."
                        ),
                        severity=NormalizedSeverity.HIGH,
                        file_path=f"runtime://{image}/sensitive-operation",
                        category="custom",
                        raw={
                            "timings": [
                                {"length": l, "time_seconds": round(t, 4)}
                                for l, t in timings
                            ]
                        },
                    )
                )

        return findings

    @staticmethod
    def _check_auth_bypass(base_url: str, image: str) -> list[Finding]:
        findings: list[Finding] = []

        try:
            url = f"{base_url}/auth-test?token=wrong"
            req = urllib.request.Request(url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body = resp.read().decode(errors="replace")
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")

            body_lower = body.lower()
            if "expected" in body_lower and (
                "bearer" in body_lower or "token" in body_lower
            ):
                findings.append(
                    Finding(
                        tool="custom-detectors",
                        rule_id="CUSTOM-AUTH-001",
                        title="Authentication endpoint leaks expected credentials",
                        description=(
                            f"The /auth-test endpoint reveals the expected token "
                            f"value in its error response. An attacker can extract "
                            f"valid credentials from the error message."
                        ),
                        severity=NormalizedSeverity.CRITICAL,
                        file_path=f"runtime://{image}/auth-test",
                        category="custom",
                    )
                )
        except Exception:
            pass

        return findings


def _has_stack_trace(body: str) -> bool:
    indicators = [
        "Traceback (most recent call last)",
        'File "',
        "line ",
        "raise ",
        "Exception:",
        "Error:",
        "at com.",
        "at java.",
        "at org.",
        "NullPointerException",
        "StackTrace",
    ]
    matches = sum(1 for ind in indicators if ind in body)
    return matches >= 2
