"""Container / image vulnerability scanner for runtime mode.

Uses Trivy to scan Docker images for OS-level and application-level CVEs.
"""

from __future__ import annotations

import json
import logging
from typing import ClassVar

from security_toolkit.core.models import (
    Finding,
    ScanMode,
    TargetProfile,
    normalize_severity,
)
from security_toolkit.core.plugin import ScannerPlugin
from security_toolkit.core.sandbox import run_with_limits
from security_toolkit.utils.process_utils import check_tool_available

logger = logging.getLogger(__name__)


class ContainerScanner(ScannerPlugin):
    """Scan a Docker image for OS and library vulnerabilities."""

    name: ClassVar[str] = "container-scanner"
    scan_modes: ClassVar[set[str]] = {ScanMode.RUNTIME}

    def can_handle(self, profile: TargetProfile) -> bool:
        if profile.image is None:
            return False
        if not check_tool_available("trivy"):
            logger.warning("trivy not found on PATH -- skipping container scan")
            return False
        return True

    def execute(self, profile: TargetProfile) -> list[Finding]:
        assert profile.image is not None
        return self._run_trivy(profile.image)

    # ------------------------------------------------------------------

    @staticmethod
    def _run_trivy(image: str) -> list[Finding]:
        cmd = [
            "trivy",
            "image",
            "--format",
            "json",
            "--quiet",
            image,
        ]
        try:
            result = run_with_limits(cmd, timeout=600)
        except Exception:
            logger.exception("Trivy image scan failed")
            return []

        if not result.stdout.strip():
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error("Failed to parse Trivy image JSON")
            return []

        findings: list[Finding] = []
        for rb in data.get("Results", []):
            target = rb.get("Target", "")
            for vuln in rb.get("Vulnerabilities", []):
                findings.append(
                    Finding(
                        tool="trivy",
                        rule_id=vuln.get("VulnerabilityID", "UNKNOWN"),
                        title=f"{vuln.get('PkgName', '?')} {vuln.get('InstalledVersion', '?')}: {vuln.get('VulnerabilityID', '')}",
                        description=vuln.get("Description", ""),
                        severity=normalize_severity(vuln.get("Severity", "UNKNOWN")),
                        file_path=target,
                        category="sca",
                        raw=vuln,
                    )
                )
        return findings
