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


class TrivySCAScanner(ScannerPlugin):
    name: ClassVar[str] = "trivy-sca"
    scan_modes: ClassVar[set[str]] = {ScanMode.SOURCE}

    def can_handle(self, profile: TargetProfile) -> bool:
        if not check_tool_available("trivy"):
            logger.warning("trivy not found on PATH -- skipping SCA")
            return False
        return profile.mode == ScanMode.SOURCE and profile.path is not None

    def execute(self, profile: TargetProfile) -> list[Finding]:
        assert profile.path is not None
        cmd = [
            "trivy",
            "filesystem",
            "--format",
            "json",
            "--scanners",
            "vuln",
            "--quiet",
            str(profile.path),
        ]

        try:
            result = run_with_limits(cmd, timeout=600)
        except Exception:
            logger.exception("Trivy SCA execution failed")
            return []

        if not result.stdout.strip():
            logger.info("Trivy SCA produced no output")
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error("Failed to parse Trivy JSON output")
            return []

        return self._parse(data)
    @staticmethod
    def _parse(data: dict) -> list[Finding]:
        findings: list[Finding] = []
        results = data.get("Results", [])
        for result_block in results:
            target_file = result_block.get("Target", "")
            for vuln in result_block.get("Vulnerabilities", []):
                findings.append(
                    Finding(
                        tool="trivy",
                        rule_id=vuln.get("VulnerabilityID", "UNKNOWN"),
                        title=f"{vuln.get('PkgName', '?')} {vuln.get('InstalledVersion', '?')}: {vuln.get('VulnerabilityID', '')}",
                        description=vuln.get("Description", ""),
                        severity=normalize_severity(vuln.get("Severity", "UNKNOWN")),
                        file_path=target_file,
                        category="sca",
                        raw=vuln,
                    )
                )
        return findings
