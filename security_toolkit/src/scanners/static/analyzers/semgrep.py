from __future__ import annotations

import json
import logging
import re
from typing import ClassVar

from security_toolkit.core.models import (
    Finding,
    NormalizedSeverity,
    ScanMode,
    TargetProfile,
    normalize_severity,
)
from security_toolkit.core.plugin import ScannerPlugin
from security_toolkit.core.sandbox import run_with_limits
from security_toolkit.utils.process_utils import check_tool_available

logger = logging.getLogger(__name__)
# False-positive reduction
# Rules known to produce high false-positive rates in internal / tool code.
# When triggered more than _FP_CONSOLIDATION_THRESHOLD times in a scan,
# they are consolidated into a single INFO-level advisory.
_NOISY_RULES: set[str] = {
    "dynamic-urllib-use-detected",
}

# If a noisy rule fires this many times or more, consolidate into one finding.
_FP_CONSOLIDATION_THRESHOLD = 3

# File-path patterns where urllib usage is expected (internal tooling,
# plugins, tests, utilities) -- NOT user-facing web handlers.
_SAFE_URLLIB_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"plugins/"),
    re.compile(r"tests?/"),
    re.compile(r"utils?/"),
    re.compile(r"tools?/"),
    re.compile(r"scripts?/"),
    re.compile(r"internal/"),
    re.compile(r"health[_-]?check"),
]
# Ruleset configuration
_MANDATORY_RULESETS: list[str] = [
    "p/security-audit",
    "p/secrets",
    "p/owasp-top-ten",
    "p/ci",
    "p/supply-chain",
]

_LANGUAGE_RULESETS: dict[str, str] = {
    "python": "p/python",
    "javascript": "p/javascript",
    "typescript": "p/typescript",
    "go": "p/golang",
    "rust": "p/rust",
    "java": "p/java",
    "ruby": "p/ruby",
    "php": "p/php",
    "c": "p/c",
    "csharp": "p/csharp",
    "kotlin": "p/kotlin",
    "scala": "p/scala",
    "swift": "p/swift",
    "bash": "p/bash",
    "elixir": "p/elixir",
}
# Plugin
class SemgrepScanner(ScannerPlugin):
    name: ClassVar[str] = "semgrep"
    scan_modes: ClassVar[set[str]] = {ScanMode.SOURCE}

    def can_handle(self, profile: TargetProfile) -> bool:
        if not check_tool_available("semgrep"):
            logger.warning("semgrep not found on PATH -- skipping SAST")
            return False
        return profile.mode == ScanMode.SOURCE and profile.path is not None

    def execute(self, profile: TargetProfile) -> list[Finding]:
        assert profile.path is not None
        rulesets = self._build_rulesets(profile)
        logger.info("Semgrep rulesets: %s", rulesets)

        raw_results = self._run_semgrep(profile, rulesets)
        return self._parse_results(raw_results)
    # Internal
    @staticmethod
    def _build_rulesets(profile: TargetProfile) -> list[str]:
        rulesets = list(_MANDATORY_RULESETS)
        for lang in profile.languages:
            rs = _LANGUAGE_RULESETS.get(lang)
            if rs and rs not in rulesets:
                rulesets.append(rs)
        return rulesets

    @staticmethod
    def _run_semgrep(
        profile: TargetProfile,
        rulesets: list[str],
    ) -> list[dict]:
        cmd = ["semgrep", "scan", "--json", "--quiet", "--no-git-ignore"]
        for rs in rulesets:
            cmd.extend(["--config", rs])
        cmd.append(str(profile.path))

        try:
            result = run_with_limits(cmd, timeout=600)
        except Exception:
            logger.exception("Semgrep execution failed")
            return []

        if not result.stdout.strip():
            logger.warning("Semgrep produced no output (exit %d)", result.returncode)
            if result.stderr:
                logger.debug("Semgrep stderr: %s", result.stderr[:2000])
            return []

        try:
            data = json.loads(result.stdout)
            return data.get("results", [])
        except json.JSONDecodeError:
            logger.error("Failed to parse Semgrep JSON output")
            return []

    @staticmethod
    def _parse_results(raw_results: list[dict]) -> list[Finding]:
        findings: list[Finding] = []
        for r in raw_results:
            extra = r.get("extra", {})
            severity_raw = extra.get("severity", "warning")
            findings.append(
                Finding(
                    tool="semgrep",
                    rule_id=r.get("check_id", "unknown"),
                    title=extra.get("message", r.get("check_id", "Semgrep finding")),
                    description=extra.get("message", ""),
                    severity=normalize_severity(severity_raw),
                    file_path=r.get("path", ""),
                    line=r.get("start", {}).get("line", 0),
                    category="sast",
                    raw=r,
                )
            )
        return SemgrepScanner._reduce_false_positives(findings)
    # False-positive reduction
    @staticmethod
    def _reduce_false_positives(findings: list[Finding]) -> list[Finding]:
        # Partition: noisy vs clean
        noisy_buckets: dict[str, list[Finding]] = {}
        clean: list[Finding] = []

        for f in findings:
            rule_short = f.rule_id.rsplit(".", 1)[-1] if "." in f.rule_id else f.rule_id
            if rule_short in _NOISY_RULES:
                noisy_buckets.setdefault(rule_short, []).append(f)
            else:
                clean.append(f)

        # Process each noisy bucket
        for rule_short, bucket in noisy_buckets.items():
            if len(bucket) < _FP_CONSOLIDATION_THRESHOLD:
                # Below threshold -- keep as-is
                clean.extend(bucket)
                continue

            # Check if all hits are in safe paths
            safe_hits: list[Finding] = []
            unsafe_hits: list[Finding] = []
            for f in bucket:
                fp = f.file_path or ""
                if any(pat.search(fp) for pat in _SAFE_URLLIB_PATH_PATTERNS):
                    safe_hits.append(f)
                else:
                    unsafe_hits.append(f)

            # Keep unsafe hits at original severity
            clean.extend(unsafe_hits)

            # Consolidate safe hits into a single INFO advisory
            if safe_hits:
                locations = sorted({f"{f.file_path}:{f.line}" for f in safe_hits})
                loc_summary = ", ".join(locations[:5])
                if len(locations) > 5:
                    loc_summary += f" (+{len(locations) - 5} more)"

                clean.append(
                    Finding(
                        tool="semgrep",
                        rule_id=f"FP-CONSOLIDATED-{rule_short}",
                        title=(
                            f"Consolidated: {len(safe_hits)} '{rule_short}' "
                            f"findings in internal/tool code (likely false positives)"
                        ),
                        description=(
                            f"Semgrep rule '{rule_short}' fired {len(safe_hits)} "
                            f"time(s) in internal tooling paths. These typically "
                            f"flag safe usage of urllib for health checks, API "
                            f"calls to localhost, or test fixtures. Locations: "
                            f"{loc_summary}"
                        ),
                        severity=NormalizedSeverity.INFO,
                        file_path=safe_hits[0].file_path,
                        line=safe_hits[0].line,
                        category="sast",
                    )
                )
                logger.info(
                    "FP reduction: consolidated %d '%s' findings in safe paths "
                    "into 1 INFO advisory",
                    len(safe_hits),
                    rule_short,
                )

        return clean
