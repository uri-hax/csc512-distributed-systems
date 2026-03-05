from __future__ import annotations

import sys
from typing import TextIO

from security_toolkit.core.models import NormalizedSeverity, ScanReport
# Severity -> colour mapping (rich markup)
_SEVERITY_STYLE: dict[NormalizedSeverity, str] = {
    NormalizedSeverity.CRITICAL: "bold white on red",
    NormalizedSeverity.HIGH: "bold red",
    NormalizedSeverity.MEDIUM: "bold yellow",
    NormalizedSeverity.LOW: "cyan",
    NormalizedSeverity.INFO: "dim",
}

_SEVERITY_LABEL: dict[NormalizedSeverity, str] = {
    NormalizedSeverity.CRITICAL: "CRITICAL",
    NormalizedSeverity.HIGH: "HIGH",
    NormalizedSeverity.MEDIUM: "MEDIUM",
    NormalizedSeverity.LOW: "LOW",
    NormalizedSeverity.INFO: "INFO",
}
# Verdict
_PASS_THRESHOLD = NormalizedSeverity.HIGH  # HIGH or above = fail


def _verdict(report: ScanReport) -> tuple[str, str]:
    if any(f.severity >= _PASS_THRESHOLD for f in report.findings):
        return "FAIL", "bold white on red"
    if report.findings:
        return "WARN", "bold yellow"
    return "PASS", "bold green"
# Rich renderer
def _render_rich(report: ScanReport) -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console(stderr=False)
    counts = report.severity_counts()
    verdict_label, verdict_style = _verdict(report)

    # Header panel
    console.print()
    console.print(
        Panel(
            f"[bold]Security Scan Report[/bold]\n"
            f"Target: [cyan]{report.target}[/cyan]  |  Mode: [cyan]{report.mode}[/cyan]\n"
            f"Started: {report.started_at}  |  Finished: {report.finished_at}",
            title="security_toolkit",
            border_style="blue",
        )
    )

    # Summary table
    summary = Table(title="Severity Summary", show_header=True, header_style="bold")
    summary.add_column("Severity", style="bold", width=12)
    summary.add_column("Count", justify="right", width=8)
    for sev in reversed(list(NormalizedSeverity)):
        style = _SEVERITY_STYLE[sev]
        summary.add_row(
            f"[{style}]{_SEVERITY_LABEL[sev]}[/{style}]",
            str(counts.get(sev.name, 0)),
        )
    summary.add_row("[bold]TOTAL[/bold]", f"[bold]{len(report.findings)}[/bold]")
    console.print(summary)

    # Findings table (top 30)
    if report.findings:
        findings_table = Table(
            title=f"Findings (showing {min(len(report.findings), 30)} of {len(report.findings)})",
            show_header=True,
            header_style="bold",
            expand=True,
        )
        findings_table.add_column("Sev", width=10)
        findings_table.add_column("Tool", width=14)
        findings_table.add_column("Rule", width=22)
        findings_table.add_column("Title", ratio=2)
        findings_table.add_column("Location", ratio=1)

        for f in report.findings[:30]:
            style = _SEVERITY_STYLE.get(f.severity, "")
            location = f.file_path or ""
            if f.line:
                location += f":{f.line}"
            findings_table.add_row(
                f"[{style}]{_SEVERITY_LABEL.get(f.severity, '?')}[/{style}]",
                f.tool,
                f.rule_id[:22],
                f.title[:80],
                location[:50],
            )
        console.print(findings_table)

    # Errors
    if report.errors:
        console.print(f"\n[bold red]Errors ({len(report.errors)}):[/bold red]")
        for err in report.errors:
            console.print(f"  [red]- {err}[/red]")

    # Verdict
    console.print()
    console.print(
        Panel(
            f"[{verdict_style}]  {verdict_label}  [/{verdict_style}]",
            title="Verdict",
            border_style="blue",
        )
    )
    console.print()
# Plain-text fallback
def _render_plain(report: ScanReport, stream: TextIO | None = None) -> None:
    out = stream or sys.stdout
    counts = report.severity_counts()
    verdict_label, _ = _verdict(report)

    out.write("\n")
    out.write("=" * 60 + "\n")
    out.write("  SECURITY SCAN REPORT\n")
    out.write(f"  Target: {report.target}  |  Mode: {report.mode}\n")
    out.write(f"  {report.started_at} -> {report.finished_at}\n")
    out.write("=" * 60 + "\n\n")

    out.write("Severity Summary:\n")
    for sev in reversed(list(NormalizedSeverity)):
        out.write(f"  {_SEVERITY_LABEL[sev]:>10}: {counts.get(sev.name, 0)}\n")
    out.write(f"  {'TOTAL':>10}: {len(report.findings)}\n\n")

    if report.findings:
        out.write(f"Findings (top 30 of {len(report.findings)}):\n")
        out.write("-" * 60 + "\n")
        for f in report.findings[:30]:
            loc = f.file_path or ""
            if f.line:
                loc += f":{f.line}"
            out.write(
                f"  [{_SEVERITY_LABEL.get(f.severity, '?'):>8}] "
                f"{f.tool:<14} {f.rule_id:<22} {f.title[:50]}\n"
                f"           Location: {loc}\n"
            )
        out.write("-" * 60 + "\n")

    if report.errors:
        out.write(f"\nErrors ({len(report.errors)}):\n")
        for err in report.errors:
            out.write(f"  - {err}\n")

    out.write(f"\nVerdict: {verdict_label}\n\n")
# Public API
def print_console_report(report: ScanReport) -> None:
    try:
        import rich  # noqa: F401

        _render_rich(report)
    except ImportError:
        _render_plain(report)
