from __future__ import annotations

import json
import logging
import subprocess
import time
import uuid
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# Ports commonly used by web services
_WEB_PORTS = {80, 443, 8080, 8443, 3000, 5000, 8000, 9000}

# Number of concurrent workers and total requests per endpoint
_CONCURRENT_WORKERS = 10
_REQUESTS_PER_ENDPOINT = 50


class LoadTester(ScannerPlugin):
    name: ClassVar[str] = "load-tester"
    scan_modes: ClassVar[set[str]] = {ScanMode.RUNTIME}

    # Check if this scanner can run for the given target
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
                    logger.warning("Service not reachable for load testing")
                    return []
                image_label = profile.image or profile.service_url
                return self._run_load_tests(base_url, image_label)

            # Otherwise start a container from the image
            assert profile.image is not None
            container_name, host_port = self._start_service(
                profile.image, profile.exposed_ports
            )
            if not container_name or not host_port:
                return []

            base_url = f"http://localhost:{host_port}"
            if not self._wait_for_health(base_url):
                logger.warning("Service did not become healthy for load testing")
                return []

            return self._run_load_tests(base_url, profile.image)

        except Exception:
            logger.exception("Load testing failed")
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

        container_name = f"sectoolkit_load_{uuid.uuid4().hex[:8]}"
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
            logger.error("Failed to start load test target: %s", result.stderr)
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
            "Load test target running: %s -> localhost:%d", container_name, host_port
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
    def _run_load_tests(base_url: str, image: str) -> list[Finding]:
        findings: list[Finding] = []

        # Test 1: Counter race condition (/increment endpoint)
        race_finding = LoadTester._test_counter_race(base_url, image)
        if race_finding:
            findings.append(race_finding)

        # Test 2: Concurrent resource allocation
        resource_finding = LoadTester._test_resource_exhaustion(base_url, image)
        if resource_finding:
            findings.append(resource_finding)

        return findings

    @staticmethod
    def _test_counter_race(base_url: str, image: str) -> Finding | None:
        increment_url = f"{base_url}/increment"

        # Verify endpoint exists
        try:
            req = urllib.request.Request(increment_url, method="GET")
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            logger.debug("No /increment endpoint found, skipping counter race test")
            return None

        responses: list[int] = []

        def _hit_increment() -> int | None:
            try:
                req = urllib.request.Request(increment_url, method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    return data.get("counter")
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=_CONCURRENT_WORKERS) as pool:
            futures = [
                pool.submit(_hit_increment) for _ in range(_REQUESTS_PER_ENDPOINT)
            ]
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    responses.append(result)

        if not responses:
            return None

        # Check for race condition: if counter was atomic, all values
        # should be unique. Duplicates indicate lost updates.
        unique_values = set(responses)
        total = len(responses)
        duplicates = total - len(unique_values)

        if duplicates > 0:
            expected_max = max(responses)
            return Finding(
                tool="load-tester",
                rule_id="RACE-001",
                title="Race condition detected: non-atomic counter increment",
                description=(
                    f"Sent {total} concurrent requests to /increment. "
                    f"Expected {total} unique counter values but found "
                    f"{len(unique_values)} unique values ({duplicates} duplicates). "
                    f"This indicates a TOCTOU race condition where concurrent "
                    f"reads and writes to the global counter are not properly "
                    f"synchronized. Max counter value: {expected_max}, "
                    f"expected: >= {total}."
                ),
                severity=NormalizedSeverity.HIGH,
                file_path=f"runtime://{image}/increment",
                category="race-condition",
                raw={
                    "total_requests": total,
                    "unique_responses": len(unique_values),
                    "duplicates": duplicates,
                    "max_counter": expected_max,
                },
            )

        logger.info("Counter race test passed (%d unique values)", len(unique_values))
        return None

    @staticmethod
    def _test_resource_exhaustion(base_url: str, image: str) -> Finding | None:
        allocate_url = f"{base_url}/allocate?size=100000"

        # Verify endpoint exists
        try:
            req = urllib.request.Request(allocate_url, method="GET")
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            return None

        success_count = 0

        def _hit_allocate() -> bool:
            try:
                req = urllib.request.Request(allocate_url, method="GET")
                with urllib.request.urlopen(req, timeout=10):
                    return True
            except Exception:
                return False

        with ThreadPoolExecutor(max_workers=_CONCURRENT_WORKERS) as pool:
            futures = [pool.submit(_hit_allocate) for _ in range(20)]
            for future in as_completed(futures):
                if future.result():
                    success_count += 1

        if success_count >= 15:
            return Finding(
                tool="load-tester",
                rule_id="RACE-002",
                title="No rate limiting on resource allocation endpoint",
                description=(
                    f"Sent 20 concurrent requests to /allocate and "
                    f"{success_count} succeeded. The endpoint accepts unbounded "
                    f"concurrent allocation requests with no rate limiting, "
                    f"which could lead to resource exhaustion (DoS)."
                ),
                severity=NormalizedSeverity.MEDIUM,
                file_path=f"runtime://{image}/allocate",
                category="race-condition",
                raw={"total_requests": 20, "successful": success_count},
            )

        return None
