from __future__ import annotations

import logging
import subprocess
import time
import uuid
from typing import ClassVar

from security_toolkit.core.models import (
    Finding,
    NormalizedSeverity,
    ScanMode,
    TargetProfile,
)
from security_toolkit.core.plugin import ScannerPlugin
from security_toolkit.core.sandbox import stop_and_remove_container
from security_toolkit.utils.docker_utils import docker_available, get_image_digest

logger = logging.getLogger(__name__)


class DriftDetector(ScannerPlugin):
    name: ClassVar[str] = "drift-detector"
    scan_modes: ClassVar[set[str]] = {ScanMode.RUNTIME}

    def can_handle(self, profile: TargetProfile) -> bool:
        if profile.image is None:
            return False
        return docker_available()

    def execute(self, profile: TargetProfile) -> list[Finding]:
        assert profile.image is not None
        findings: list[Finding] = []

        # Get the expected digest from the image metadata
        expected_digest = get_image_digest(profile.image)
        if not expected_digest:
            logger.warning("Could not determine image digest for %s", profile.image)
            return findings

        managed_container: str | None = None

        try:
            # Check if any containers running this image have filesystem changes
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-q",
                    "--filter",
                    f"ancestor={profile.image}",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            container_ids = result.stdout.strip().split("\n")
            container_ids = [c for c in container_ids if c]

            # If no containers are running, start one temporarily
            if not container_ids:
                logger.info(
                    "No running containers for image %s -- starting temporary container",
                    profile.image,
                )
                managed_container = self._start_temp_container(profile.image)
                if managed_container:
                    # Let the app initialise and create runtime artifacts
                    time.sleep(5)
                    container_ids = [managed_container]
                else:
                    logger.warning("Could not start temporary container for drift check")
                    return findings

            for cid in container_ids:
                diff_result = subprocess.run(
                    ["docker", "diff", cid],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                changes = diff_result.stdout.strip()
                if changes:
                    changed_files = [
                        line
                        for line in changes.split("\n")
                        if line
                        and not line.startswith("C /")  # Skip directory-only changes
                    ]
                    if changed_files:
                        findings.append(
                            Finding(
                                tool="drift-detector",
                                rule_id="DRIFT-001",
                                title=f"Filesystem drift detected in container {cid[:12]}",
                                description=(
                                    f"Container {cid[:12]} based on image {profile.image} "
                                    f"has {len(changed_files)} unexpected filesystem change(s). "
                                    f"This may indicate runtime tampering or uncontrolled "
                                    f"file mutations (e.g., .pyc generation, temp files, logs).\n"
                                    f"Changed files: {'; '.join(changed_files[:10])}"
                                    + (f"\n... and {len(changed_files) - 10} more" if len(changed_files) > 10 else "")
                                ),
                                severity=NormalizedSeverity.HIGH,
                                file_path=f"container://{cid[:12]}",
                                category="drift",
                                raw={
                                    "container_id": cid,
                                    "image": profile.image,
                                    "expected_digest": expected_digest,
                                    "changed_files": changed_files[:50],
                                    "total_changes": len(changed_files),
                                },
                            )
                        )

        except Exception:
            logger.exception("Drift detection failed for %s", profile.image)
        finally:
            if managed_container:
                stop_and_remove_container(managed_container)

        return findings

    @staticmethod
    def _start_temp_container(image: str) -> str | None:
        container_name = f"sectoolkit_drift_{uuid.uuid4().hex[:8]}"
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--cpus", "0.5",
            "--memory", "256m",
            "--pids-limit", "128",
            "--security-opt", "no-new-privileges",
            image,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error("Failed to start drift temp container: %s", result.stderr)
            return None
        logger.info("Started temporary drift container: %s", container_name)
        return container_name
