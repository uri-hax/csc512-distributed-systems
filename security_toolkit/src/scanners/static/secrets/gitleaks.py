# Gitleaks secret scanner: detects hardcoded credentials in git history and source files
# Dependencies: gitleaks CLI tool
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

from security_toolkit.core.models import (
    Finding,
    NormalizedSeverity,
    ScanMode,
    TargetProfile,
)
from security_toolkit.core.plugin import ScannerPlugin
from security_toolkit.utils.process_utils import check_tool_available

logger = logging.getLogger(__name__)

# Severity mapping: gitleaks doesn't output severity per-rule,
# but all secret leaks are at least HIGH (credentials = direct compromise).
_RULE_SEVERITY: dict[str, NormalizedSeverity] = {
    # AWS
    "aws-access-token": NormalizedSeverity.CRITICAL,
    "aws-secret-access-key": NormalizedSeverity.CRITICAL,
    # Private keys
    "private-key": NormalizedSeverity.CRITICAL,
    "rsa-private-key": NormalizedSeverity.CRITICAL,
    # Database
    "generic-api-key": NormalizedSeverity.HIGH,
    "generic-password": NormalizedSeverity.HIGH,
    # Tokens
    "github-pat": NormalizedSeverity.CRITICAL,
    "github-fine-grained-pat": NormalizedSeverity.CRITICAL,
    "github-oauth": NormalizedSeverity.CRITICAL,
    "gitlab-pat": NormalizedSeverity.CRITICAL,
    "slack-token": NormalizedSeverity.HIGH,
    "slack-webhook": NormalizedSeverity.HIGH,
    "stripe-api-key": NormalizedSeverity.CRITICAL,
    "twilio-api-key": NormalizedSeverity.HIGH,
    "sendgrid-api-key": NormalizedSeverity.HIGH,
    "npm-access-token": NormalizedSeverity.HIGH,
    "pypi-upload-token": NormalizedSeverity.HIGH,
    "hashicorp-tf-api-token": NormalizedSeverity.HIGH,
    "jwt": NormalizedSeverity.HIGH,
}


class GitleaksScanner(ScannerPlugin):
    name: ClassVar[str] = "gitleaks"
    scan_modes: ClassVar[set[str]] = {ScanMode.SOURCE}

    # Check if this scanner can run for the given target
    def can_handle(self, profile: TargetProfile) -> bool:
        if profile.path is None:
            return False
        if not check_tool_available("gitleaks"):
            logger.warning("gitleaks not found on PATH -- skipping secret scan")
            return False
        # Only run if the target has a .git directory (otherwise nothing to scan)
        git_dir = profile.path / ".git"
        if not git_dir.is_dir():
            logger.info(
                "No .git directory in %s -- scanning working tree only", profile.path
            )
            # Still useful: scan files even without git history
            return True
        return True

    # Run the scan and return findings
    def execute(self, profile: TargetProfile) -> list[Finding]:
        assert profile.path is not None

        try:
            findings = self._run_gitleaks(profile.path)
            logger.info("Gitleaks returned %d finding(s)", len(findings))
            return findings
        except Exception:
            logger.exception("Gitleaks scan failed")
            return []
    # Scanner
    @staticmethod
    def _run_gitleaks(target: Path) -> list[Finding]:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="gitleaks_"
        ) as f:
            output_file = f.name

        git_dir = target / ".git"
        if git_dir.is_dir():
            # Full git history scan
            cmd = [
                "gitleaks",
                "detect",
                "--source",
                str(target),
                "--report-format",
                "json",
                "--report-path",
                output_file,
                "--no-banner",
            ]
        else:
            # No git history -- scan files only
            cmd = [
                "gitleaks",
                "detect",
                "--source",
                str(target),
                "--no-git",
                "--report-format",
                "json",
                "--report-path",
                output_file,
                "--no-banner",
            ]

        try:
            # gitleaks exits 1 when leaks are found; that's expected
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            # Exit code 0 = no leaks, 1 = leaks found, other = error
            if result.returncode not in (0, 1):
                logger.error(
                    "Gitleaks failed (exit %d): %s",
                    result.returncode,
                    result.stderr[:500],
                )
                return []
        except subprocess.TimeoutExpired:
            logger.error("Gitleaks timed out after 300s")
            return []
        except Exception:
            logger.exception("Failed to execute gitleaks")
            return []

        # Parse results
        findings: list[Finding] = []
        try:
            content = Path(output_file).read_text(encoding="utf-8").strip()
            if not content:
                return []

            results = json.loads(content)
            if not isinstance(results, list):
                return []

            for entry in results:
                rule_id = entry.get("RuleID", "unknown")
                file_path = entry.get("File", "")
                line = entry.get("StartLine", 0)
                commit = entry.get("Commit", "")[:12]
                author = entry.get("Author", "")
                date = entry.get("Date", "")
                match_val = entry.get("Match", "")

                # Determine severity from rule
                severity = _RULE_SEVERITY.get(rule_id, NormalizedSeverity.HIGH)

                # Build descriptive title and description
                secret_type = entry.get(
                    "Description", rule_id.replace("-", " ").title()
                )

                if commit:
                    title = f"Secret leaked in Git history: {secret_type}"
                    description = (
                        f"Gitleaks detected a {secret_type} in the Git repository. "
                        f"Commit: {commit} by {author} on {date}. "
                        f"File: {file_path}:{line}. "
                        f"Even if removed from the current tree, the secret "
                        f"exists in Git history and should be rotated immediately."
                    )
                else:
                    title = f"Secret detected in source: {secret_type}"
                    description = (
                        f"Gitleaks detected a {secret_type} in {file_path}:{line}. "
                        f"This secret should be removed and rotated."
                    )

                findings.append(
                    Finding(
                        tool="gitleaks",
                        rule_id=rule_id,
                        title=title,
                        description=description,
                        severity=severity,
                        file_path=file_path,
                        line=line,
                        category="secrets",
                        raw=entry,
                    )
                )
        except json.JSONDecodeError:
            logger.exception("Failed to parse gitleaks JSON output")
        finally:
            Path(output_file).unlink(missing_ok=True)

        return findings
