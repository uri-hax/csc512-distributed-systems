from __future__ import annotations

import logging
from pathlib import Path

from security_toolkit.core.models import NormalizedSeverity, ScanReport

logger = logging.getLogger(__name__)

_SEVERITY_EMOJI = {
    NormalizedSeverity.CRITICAL: "CRITICAL",
    NormalizedSeverity.HIGH: "HIGH",
    NormalizedSeverity.MEDIUM: "MEDIUM",
    NormalizedSeverity.LOW: "LOW",
    NormalizedSeverity.INFO: "INFO",
}


def write_markdown_report(
    report: ScanReport,
    output_path: Path,
    *,
    include_raw: bool = False,
) -> Path:
    output_path = output_path.resolve()

    # If path is a directory, use report.md
    if output_path.is_dir() or (not output_path.suffix and not output_path.exists()):
        output_path = output_path / "report.md"
    # If path has no suffix, add .md extension
    elif not output_path.suffix:
        output_path = output_path.with_suffix(".md")
    # If already .md, use as-is (no timestamp)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = _render_markdown(report, include_raw=include_raw)
    output_path.write_text(content, encoding="utf-8")
    logger.info("Markdown report written to %s", output_path)
    return output_path


def _render_markdown(report: ScanReport, *, include_raw: bool = False) -> str:
    counts = report.severity_counts()
    verdict = _verdict(report)
    lines: list[str] = []

    # Header
    lines.append("# Security Scan Report")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| **Target** | `{report.target}` |")
    lines.append(f"| **Mode** | {report.mode} |")
    lines.append(f"| **Started** | {report.started_at} |")
    lines.append(f"| **Finished** | {report.finished_at} |")
    lines.append(f"| **Verdict** | **{verdict}** |")
    lines.append(f"| **Total Findings** | {len(report.findings)} |")
    lines.append("")

    # Severity summary
    lines.append("## Severity Summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    for sev in reversed(list(NormalizedSeverity)):
        count = counts.get(sev.name, 0)
        if count > 0:
            lines.append(f"| **{sev.name}** | {count} |")
        else:
            lines.append(f"| {sev.name} | {count} |")
    lines.append(f"| **TOTAL** | **{len(report.findings)}** |")
    lines.append("")

    # Plugin execution status
    if report.plugin_execution:
        lines.append("## Plugin Execution Status")
        lines.append("")

        executed = []
        failed = []
        skipped = []
        for name, info in report.plugin_execution.items():
            status = info.get("status", "unknown")
            if status == "success":
                executed.append((name, info))
            elif status == "failed":
                failed.append((name, info))
            elif status == "skipped":
                skipped.append((name, info))

        lines.append("| Plugin | Status | Findings | Details |")
        lines.append("|--------|--------|----------|---------|")
        for name, info in executed:
            fc = info.get("findings_count", 0)
            lines.append(f"| {name} | **Executed** | {fc} | - |")
        for name, info in failed:
            err = info.get("error", "Unknown error")
            lines.append(f"| {name} | **Failed** | 0 | {err} |")
        for name, info in skipped:
            reason = info.get("reason", "Unknown reason")
            lines.append(f"| {name} | Skipped | 0 | {reason} |")
        lines.append("")

        lines.append(
            f"**Summary:** {len(executed)} executed, "
            f"{len(failed)} failed, {len(skipped)} skipped "
            f"(out of {len(report.plugin_execution)} registered)"
        )
        lines.append("")

    # Findings by category
    if report.findings:
        grouped: dict[str, list] = {}
        for f in report.findings:
            cat = f.category or "other"
            grouped.setdefault(cat, []).append(f)

        lines.append("## Findings by Category")
        lines.append("")

        for category, findings in sorted(grouped.items()):
            lines.append(f"### {category.upper()} ({len(findings)} finding(s))")
            lines.append("")

            for i, f in enumerate(findings, 1):
                location = f.file_path or ""
                if f.line:
                    location += f":{f.line}"

                lines.append(
                    f"#### {i}. [{_SEVERITY_EMOJI.get(f.severity, '?')}] {f.title}"
                )
                lines.append("")
                lines.append(f"| Property | Value |")
                lines.append(f"|----------|-------|")
                lines.append(f"| **Severity** | {f.severity.name} |")
                lines.append(f"| **Tool** | {f.tool} |")
                lines.append(f"| **Rule ID** | `{f.rule_id}` |")
                lines.append(f"| **Location** | `{location}` |")
                lines.append(f"| **Fingerprint** | `{f.fingerprint}` |")
                lines.append("")
                lines.append(f"**Description:** {f.description}")
                lines.append("")

                if include_raw and f.raw:
                    lines.append("<details>")
                    lines.append("<summary>Raw vendor data</summary>")
                    lines.append("")
                    lines.append("```json")
                    import json

                    lines.append(json.dumps(f.raw, indent=2, default=str))
                    lines.append("```")
                    lines.append("</details>")
                    lines.append("")

                lines.append("---")
                lines.append("")
    else:
        lines.append("## Findings")
        lines.append("")
        lines.append("No findings detected.")
        lines.append("")

    # Errors
    if report.errors:
        lines.append("## Errors")
        lines.append("")
        for err in report.errors:
            lines.append(f"- {err}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by security-toolkit*")
    lines.append("")

    return "\n".join(lines)


def _verdict(report: ScanReport) -> str:
    if any(f.severity >= NormalizedSeverity.HIGH for f in report.findings):
        return "FAIL"
    if report.findings:
        return "WARN"
    return "PASS"
