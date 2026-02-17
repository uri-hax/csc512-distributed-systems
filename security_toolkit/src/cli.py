"""CLI entry point for ``security_toolkit``.

Usage examples::

    # Source mode -- scan a local directory
    security_toolkit scan --target ./my-repo

    # Runtime mode -- scan a Docker image
    security_toolkit inspect --image my-app:latest

    # Runtime mode -- inspect a running process
    security_toolkit inspect --pid 12345

    # Full mode -- combined source + runtime scan
    security_toolkit full --target ./my-repo --image my-app:latest

    # Write JSON report to file
    security_toolkit scan --target ./my-repo --output report.json
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from security_toolkit import __version__
from security_toolkit.core.engine import ScanEngine
from security_toolkit.core.models import NormalizedSeverity, ScanMode, ScanReport
from security_toolkit.core.profiler import profile_target
from security_toolkit.reporting.console_report import print_console_report
from security_toolkit.reporting.json_report import write_json_report
from security_toolkit.reporting.markdown_report import write_markdown_report

logger = logging.getLogger("security_toolkit")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add --output, --workers, --fail-on, --include-raw to a subparser."""
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Path to write JSON report (default: stdout summary only).",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Number of parallel plugin workers (default: 4).",
    )
    parser.add_argument(
        "--fail-on",
        choices=["critical", "high", "medium", "low", "info"],
        default="high",
        help="Exit with code 1 if any finding meets or exceeds this severity (default: high).",
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        default=False,
        help="Include raw vendor JSON in the report output (verbose; off by default).",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="security_toolkit",
        description="Security analysis toolkit -- SAST, SCA, IaC, DAST, and memory forensics.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (-v = INFO, -vv = DEBUG).",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- scan (source mode) ------------------------------------------------
    scan_parser = sub.add_parser(
        "scan",
        help="Run static analysis on a source directory.",
    )
    scan_parser.add_argument(
        "--target",
        "-t",
        required=True,
        help="Path to the directory to scan.",
    )
    _add_common_args(scan_parser)

    # --- inspect (runtime mode) --------------------------------------------
    inspect_parser = sub.add_parser(
        "inspect",
        help="Inspect a Docker image, running process, or live service.",
    )
    inspect_group = inspect_parser.add_mutually_exclusive_group(required=False)
    inspect_group.add_argument(
        "--image",
        "-i",
        help="Docker image reference (e.g. my-app:latest).",
    )
    inspect_group.add_argument(
        "--pid",
        "-p",
        type=int,
        help="PID of a running process to inspect.",
    )
    inspect_parser.add_argument(
        "--url",
        "-u",
        default=None,
        help=(
            "URL of a running service (e.g. http://localhost:5000). "
            "HTTP-based plugins (DAST, ZAP, load-tester, custom-detectors) "
            "connect directly instead of starting a container. "
            "Can be combined with --image for Docker-specific plugins."
        ),
    )
    _add_common_args(inspect_parser)

    # --- full (source + runtime combined) ----------------------------------
    full_parser = sub.add_parser(
        "full",
        help="Run both source and runtime analysis, producing a single merged report.",
    )
    full_parser.add_argument(
        "--target",
        "-t",
        required=True,
        help="Path to the source directory to scan.",
    )
    full_parser.add_argument(
        "--image",
        "-i",
        default=None,
        help="Docker image reference (e.g. my-app:latest).",
    )
    full_parser.add_argument(
        "--url",
        "-u",
        default=None,
        help=(
            "URL of a running service for runtime plugins. "
            "When used with --image, HTTP plugins hit the URL directly "
            "while Docker plugins inspect the image. "
            "When used alone, only HTTP-based runtime plugins run."
        ),
    )
    _add_common_args(full_parser)

    return parser


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Fail-on logic
# ---------------------------------------------------------------------------

_FAIL_ON_MAP: dict[str, NormalizedSeverity] = {
    "critical": NormalizedSeverity.CRITICAL,
    "high": NormalizedSeverity.HIGH,
    "medium": NormalizedSeverity.MEDIUM,
    "low": NormalizedSeverity.LOW,
    "info": NormalizedSeverity.INFO,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    engine = ScanEngine(max_workers=args.workers)

    # --- Profile target(s) -------------------------------------------------
    try:
        if args.command == "scan":
            profile = profile_target(target=args.target)
            logger.info("Target profile: %s", profile)
            report = engine.run(profile)

        elif args.command == "inspect":
            url = getattr(args, "url", None)
            if not args.image and not args.pid and not url:
                parser.error(
                    "inspect requires at least one of --image, --pid, or --url"
                )
            profile = profile_target(
                image=args.image, pid=args.pid, url=url
            )
            logger.info("Target profile: %s", profile)
            report = engine.run(profile)

        elif args.command == "full":
            url = getattr(args, "url", None)
            if not args.image and not url:
                parser.error(
                    "full requires at least one of --image or --url "
                    "for runtime analysis"
                )

            # Run SOURCE mode
            source_profile = profile_target(target=args.target)
            logger.info("Source profile: %s", source_profile)
            source_report = engine.run(source_profile)

            # Run RUNTIME mode (image + optional url, or url only)
            runtime_profile = profile_target(
                image=args.image, url=url
            )
            logger.info("Runtime profile: %s", runtime_profile)
            runtime_report = engine.run(runtime_profile)

            # Merge into a single report
            runtime_label = args.image or url

            # Merge plugin execution: prefer "success"/"failed" over "skipped"
            merged_plugin_execution = dict(source_report.plugin_execution)
            for name, info in runtime_report.plugin_execution.items():
                existing = merged_plugin_execution.get(name)
                if existing is None:
                    merged_plugin_execution[name] = info
                elif existing.get("status") == "skipped":
                    merged_plugin_execution[name] = info
                # else: keep source (it was executed/failed there)
            report = ScanReport(
                target=f"{args.target} + {runtime_label}",
                mode=ScanMode.FULL,
                started_at=source_report.started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                findings=source_report.findings + runtime_report.findings,
                errors=source_report.errors + runtime_report.errors,
                plugin_execution=merged_plugin_execution,
            )
            report.deduplicate()
            report.sort_by_severity()

        else:
            parser.error(f"Unknown command: {args.command}")
            return  # unreachable

    except ValueError as exc:
        logger.error("Target profiling failed: %s", exc)
        sys.exit(2)

    # --- Output ------------------------------------------------------------
    print_console_report(report)

    if args.output:
        json_path = Path(args.output)

        # Normalize path: directory → report.json, no-suffix → add .json
        if json_path.is_dir() or (not json_path.suffix):
            json_path = json_path / "report.json" if json_path.is_dir() else json_path.with_suffix(".json")

        # MD path is same location, different extension
        md_path = json_path.parent / (json_path.stem + ".md")

        write_json_report(report, json_path, include_raw=args.include_raw)
        logger.info("JSON report saved to %s", json_path)

        write_markdown_report(report, md_path, include_raw=args.include_raw)
        logger.info("Markdown report saved to %s", md_path)

    # --- Exit code ---------------------------------------------------------
    fail_threshold = _FAIL_ON_MAP.get(args.fail_on, NormalizedSeverity.HIGH)
    if any(f.severity >= fail_threshold for f in report.findings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
