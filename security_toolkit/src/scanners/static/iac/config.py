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


class IaCConfigScanner(ScannerPlugin):
    name: ClassVar[str] = "iac-config"
    scan_modes: ClassVar[set[str]] = {ScanMode.SOURCE}

    def can_handle(self, profile: TargetProfile) -> bool:
        if not check_tool_available("trivy"):
            logger.warning("trivy not found on PATH -- skipping IaC config scan")
            return False
        return (
            profile.mode == ScanMode.SOURCE
            and profile.path is not None
            and (profile.has_docker or profile.has_k8s or profile.has_terraform)
        )

    def execute(self, profile: TargetProfile) -> list[Finding]:
        assert profile.path is not None
        return self._run_trivy_config(profile)
    @staticmethod
    def _run_trivy_config(profile: TargetProfile) -> list[Finding]:
        assert profile.path is not None
        cmd = [
            "trivy",
            "filesystem",
            "--format",
            "json",
            "--scanners",
            "misconfig",
            "--quiet",
            str(profile.path),
        ]
        try:
            result = run_with_limits(cmd, timeout=300)
        except Exception:
            logger.exception("Trivy IaC execution failed")
            return []

        if not result.stdout.strip():
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error("Failed to parse Trivy config JSON")
            return []

        findings: list[Finding] = []
        for result_block in data.get("Results", []):
            target = result_block.get("Target", "")
            for mc in result_block.get("Misconfigurations", []):
                findings.append(
                    Finding(
                        tool="trivy",
                        rule_id=mc.get("ID", "UNKNOWN"),
                        title=mc.get("Title", "IaC misconfiguration"),
                        description=mc.get("Description", ""),
                        severity=normalize_severity(mc.get("Severity", "UNKNOWN")),
                        file_path=target,
                        line=mc.get("CauseMetadata", {}).get("StartLine", 0),
                        category="iac",
                        raw=mc,
                    )
                )
        return findings
