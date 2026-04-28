# analyze.py
#
# Standalone comparison and export utility for saved chaos reports.
# Currently produces analysis.txt which overlaps significantly with report.txt.
#
# TODO: refactor to focus on CSV export and cross-submission aggregation
#       rather than duplicating the per-run report output.
#       Potential uses:
#         - batch comparison across a full class submission set
#         - CSV export for research analysis
#         - instructor-facing summary distinct from student report.txt
#
# Not called by run_chaos.py: run directly against a saved report:
#   python analyze.py --report chaos_reports/20260401_123456

import argparse
import json
import os
import csv
import sys
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# Load
# ═══════════════════════════════════════════════════════════════════════════════

def load_report(report_dir: str) -> list[dict]:
    """Load result.json from a report directory."""
    path = Path(report_dir) / "result.json"
    if not path.exists():
        raise FileNotFoundError(f"No result.json found in {report_dir}")
    with open(path) as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════
# Compare
# ═══════════════════════════════════════════════════════════════════════════════

def compare_to_baseline(profiles: list[dict]) -> list[dict]:
    """
    For each profile, compute deltas against the 'none' baseline.
    Returns a list of comparison dicts, one per non-baseline profile.
    """
    baseline = next((p for p in profiles if p["profile"] == "none"), None)
    if baseline is None:
        raise ValueError(
            "No 'none' baseline profile found in report. "
            "Re-run with the 'none' profile included."
        )

    comparisons = []
    for p in profiles:
        if p["profile"] == "none":
            continue

        comparison = {
            "profile":      p["profile"],
            "exit_code":    p["exit_code"],
            "oom_killed":   p["oom_killed"],
            "timed_out":    p["timed_out"],

            # Raw values
            "wall_time_s":  p["wall_time_s"],
            "peak_rss_mb":  p.get("peak_rss_mb", 0),
            "cpu_avg_pct":  p.get("cpu_avg_pct", 0),
            "blk_write_mb": p.get("blk_write_mb", 0),

            # Wall time delta vs baseline
            "wall_time_delta_s": _delta(p["wall_time_s"],
                                        baseline["wall_time_s"]),
            "wall_time_pct":     _pct_change(baseline["wall_time_s"],
                                             p["wall_time_s"]),

            # Memory delta vs baseline
            "rss_delta_mb": _delta(p.get("peak_rss_mb", 0),
                                   baseline.get("peak_rss_mb", 0)),
            "rss_pct":      _pct_change(baseline.get("peak_rss_mb", 0),
                                        p.get("peak_rss_mb", 0)),

            # CPU throughput from parsed metrics (program-reported iter/s or ops/sec)
            "cpu_avg_baseline":   _metric(baseline, "cpu_avg"),
            "cpu_avg_chaos":      _metric(p, "cpu_avg"),
            "cpu_throughput_pct": _pct_change(_metric(baseline, "cpu_avg"),
                                              _metric(p, "cpu_avg")),

            # Memory peak from parsed metrics
            "mem_peak_baseline": _metric(baseline, "mem_peak"),
            "mem_peak_chaos":    _metric(p, "mem_peak"),

            # Failure flags
            "failed": (p["exit_code"] != 0
                       or p["oom_killed"]
                       or p["timed_out"]),
            "baseline_failed": (baseline["exit_code"] != 0
                                or baseline["oom_killed"]
                                or baseline["timed_out"]),
        }
        comparisons.append(comparison)

    return comparisons


def _delta(chaos_val, baseline_val):
    return round(chaos_val - baseline_val, 2)


def _pct_change(baseline, chaos):
    if not baseline:
        return None
    return round((chaos - baseline) / baseline * 100, 1)


def _metric(profile_dict, key):
    return profile_dict.get("metrics", {}).get(key, 0) or 0


# ═══════════════════════════════════════════════════════════════════════════════
# Text output
# ═══════════════════════════════════════════════════════════════════════════════

def print_comparison(comparisons: list[dict], baseline: dict, out=None):
    """Write a human-readable comparison table to stdout"""
    import sys
    out = out or sys.stdout
    bar = "═" * 64

    out.write(f"\n{bar}\n")
    out.write("  CHAOS COMPARISON REPORT\n")
    out.write(f"  Baseline (none):\n")
    out.write(f"    wall={baseline['wall_time_s']:.1f}s  "
              f"rss={baseline.get('peak_rss_mb', 0):.1f} MB  "
              f"exit={baseline['exit_code']}  "
              f"throughput={_metric(baseline, 'cpu_avg'):.0f} ops/s\n")
    out.write(bar + "\n")

    for c in comparisons:
        if c["oom_killed"]:
            status = "OOM KILLED"
        elif c["timed_out"]:
            status = "TIMED OUT"
        elif c["failed"]:
            status = f"FAILED (exit {c['exit_code']})"
        else:
            status = "ok"

        out.write(f"\n  Profile : {c['profile']}  [{status}]\n")

        # Wall time
        wt_pct = (f"{c['wall_time_pct']:+.1f}%"
                  if c["wall_time_pct"] is not None else "n/a")
        out.write(f"  Wall time  : {c['wall_time_s']:.1f}s  "
                  f"(delta: {c['wall_time_delta_s']:+.1f}s  {wt_pct})\n")

        # CPU throughput
        if c["cpu_avg_baseline"] > 0:
            tp_pct = (f"{c['cpu_throughput_pct']:+.1f}%"
                      if c["cpu_throughput_pct"] is not None else "n/a")
            out.write(f"  Throughput : {c['cpu_avg_chaos']:.0f} ops/s  "
                      f"(baseline: {c['cpu_avg_baseline']:.0f}  {tp_pct})\n")

        # Memory
        rss_pct = (f"{c['rss_pct']:+.1f}%"
                   if c["rss_pct"] is not None else "n/a")
        out.write(f"  Memory     : {c['peak_rss_mb']:.1f} MB  "
                  f"(delta: {c['rss_delta_mb']:+.1f} MB  {rss_pct})\n")

        # Interpretation
        for note in _interpret(c):
            out.write(f"  → {note}\n")

    out.write(f"\n{bar}\n")
    _print_summary(comparisons, out)
    out.write(f"{bar}\n")


def _interpret(c: dict) -> list[str]:
    notes = []

    if c["oom_killed"]:
        notes.append("FAIL: Killed by OS — program exhausted available memory.")
        notes.append("  Check: does your program free memory on all exit paths?")
        return notes

    if c["timed_out"]:
        notes.append("FAIL: Did not finish within 3x baseline time.")
        notes.append("  Your program is too sensitive to this constraint for "
                     "production use.")
        return notes

    if c["exit_code"] != 0:
        notes.append(f"FAIL: Non-zero exit ({c['exit_code']}), check stderr.")

    wt = c.get("wall_time_pct")
    if wt is not None and wt > 200:
        notes.append(f"FAIL: Ran {wt:.0f}% slower than baseline — "
                     "program does not degrade gracefully under this constraint.")
    elif wt is not None and wt > 50:
        notes.append(f"WARN: Ran {wt:.0f}% slower: noticeable degradation.")
    elif wt is not None and wt > 20:
        notes.append(f"NOTE: Ran {wt:.0f}% slower: minor degradation.")

    rss = c.get("rss_pct")
    if rss is not None and rss > 50:
        notes.append(f"WARN: Memory {rss:.0f}% higher than baseline "
                     "check for accumulation under pressure.")

    if not notes:
        notes.append("PASS: No significant deviation from baseline.")

    return notes


def _print_summary(comparisons: list[dict], out):
    """Print an overall verdict across all profiles."""
    failures  = [c for c in comparisons if c["failed"] or
                 (c.get("wall_time_pct") or 0) > 200]
    warnings  = [c for c in comparisons if not c["failed"] and
                 20 < (c.get("wall_time_pct") or 0) <= 200]
    passing   = [c for c in comparisons if c not in failures and c not in warnings]

    out.write("\n  OVERALL VERDICT\n")
    out.write(f"  {'─' * 40}\n")
    out.write(f"  Profiles run  : {len(comparisons)}\n")
    out.write(f"  Passing       : {len(passing)}\n")
    out.write(f"  Warnings      : {len(warnings)}\n")
    out.write(f"  Failing       : {len(failures)}\n")

    if failures:
        out.write("\n  Failed profiles:\n")
        for c in failures:
            reason = ("OOM" if c["oom_killed"] else
                      "TIMEOUT" if c["timed_out"] else
                      f"exit {c['exit_code']}" if c["exit_code"] != 0 else
                      f"ran {c.get('wall_time_pct', 0):.0f}% slower")
            out.write(f"FAIL: {c['profile']:<22} {reason}\n")

    if warnings:
        out.write("\n  Profiles with warnings:\n")
        for c in warnings:
            out.write(f" WARN: {c['profile']:<22} "
                      f"ran {c.get('wall_time_pct', 0):.0f}% slower\n")

    if not failures and not warnings:
        out.write("\n SUCCESS: Program passed all chaos profiles.\n")


# ═══════════════════════════════════════════════════════════════════════════════
# CSV output
# ═══════════════════════════════════════════════════════════════════════════════

def write_csv(comparisons: list[dict], baseline: dict, output_path: str):
    """Write comparison data to CSV for further analysis."""
    fields = [
        "profile", "exit_code", "oom_killed", "timed_out", "failed",
        "wall_time_s", "wall_time_delta_s", "wall_time_pct",
        "peak_rss_mb", "rss_delta_mb", "rss_pct",
        "cpu_avg_chaos", "cpu_avg_baseline", "cpu_throughput_pct",
        "blk_write_mb",
    ]

    baseline_row = {
        "profile":            "none (baseline)",
        "exit_code":          baseline["exit_code"],
        "oom_killed":         baseline["oom_killed"],
        "timed_out":          baseline["timed_out"],
        "failed":             False,
        "wall_time_s":        baseline["wall_time_s"],
        "wall_time_delta_s":  0,
        "wall_time_pct":      0,
        "peak_rss_mb":        baseline.get("peak_rss_mb", 0),
        "rss_delta_mb":       0,
        "rss_pct":            0,
        "cpu_avg_chaos":      _metric(baseline, "cpu_avg"),
        "cpu_avg_baseline":   _metric(baseline, "cpu_avg"),
        "cpu_throughput_pct": 0,
        "blk_write_mb":       baseline.get("blk_write_mb", 0),
    }

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow(baseline_row)
        for c in comparisons:
            writer.writerow({k: c.get(k, "") for k in fields})

    print(f"CSV written to: {output_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Compare chaos profiles against the 'none' baseline.",
    )
    parser.add_argument(
        "--report", required=True,
        help="Path to report directory (e.g. chaos_reports/20260401_123456)",
    )
    parser.add_argument(
        "--format", choices=["csv", "both"], default=None,
        help="Also export to CSV (optional)",
    )
    args = parser.parse_args()

    try:
        profiles = load_report(args.report)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    baseline = next((p for p in profiles if p["profile"] == "none"), None)
    if baseline is None:
        print("Error: no 'none' baseline found. Re-run with none profile included.",
              file=sys.stderr)
        sys.exit(1)

    comparisons = compare_to_baseline(profiles)
    analysis_path = os.path.join(args.report, "analysis.txt")

    with open(analysis_path, "w") as f:
        print_comparison(comparisons, baseline, out=f)

    print(f"Analysis written to: {analysis_path}")

    if args.format in ("csv", "both"):
        csv_path = os.path.join(args.report, "comparison.csv")
        write_csv(comparisons, baseline, csv_path)


if __name__ == "__main__":
    main()