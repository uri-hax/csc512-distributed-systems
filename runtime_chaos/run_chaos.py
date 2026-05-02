# Handles both single-file submissions and full project directories.
#
# Run directly:
#   python run_chaos.py --path /path/to/submission.c
#   python run_chaos.py --path /path/to/project_dir
#   python run_chaos.py --path /path/to/submission.c --profile memory_squeeze
#
# Or import into a pipeline:
#   from run_chaos import run_chaos_on_path
#   result = run_chaos_on_path("/path/to/submission", "cpu_gradual", timeout=90)

import argparse
import os
import json
import sys
from pathlib import Path
from datetime import datetime

from chaos_config import PROFILES
from chaos_runner import run_in_container_with_chaos, ChaosRunResult

from submission_runner.docker_runner import DOCKER_IMAGES, run_in_container
from submission_runner.build import build_submission
from submission_runner.detect import detect_build_system, get_args
from submission_runner.lang_reg import LANGUAGES


LANGUAGE_MAP = {
    ext: lang
    for lang, cfg in LANGUAGES.items()
    for ext in cfg["extensions"]
}


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def run_chaos_on_path(
    path: str | Path,
    profile_name: str = "none",
    timeout: int = 120,
) -> ChaosRunResult:
    """
    Run a submission (file or directory) under a chaos profile.

    Single files (.c, .cpp, .py) are compiled/run directly.
    Directories are handed to build_submission() so Makefiles, multi-file
    projects, and build scripts all work exactly as they do in submission_runner.

    Args:
        path:         Path to a submission file or project directory
        profile_name: Chaos profile name from chaos_config.PROFILES
        timeout:      Max seconds for the run phase

    Returns:
        ChaosRunResult
    """
    target = Path(path).resolve()

    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")

    if target.is_file() and target.name == "dirs.txt":
        target = target.parent

    if target.is_file():
        return _run_single_file(target, profile_name, timeout)
    elif target.is_dir():
        return _run_directory(target, profile_name, timeout)
    else:
        raise ValueError(f"Path is neither a file nor a directory: {target}")


# ═══════════════════════════════════════════════════════════════════════════════
# Single-file path
# ═══════════════════════════════════════════════════════════════════════════════

def _run_single_file(
    path: Path,
    profile_name: str,
    timeout: int,
) -> ChaosRunResult:
    ext = path.suffix.lower()
    language = LANGUAGE_MAP.get(ext)
    if language is None:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {list(LANGUAGE_MAP)}"
        )

    submission_dir = str(path.parent)
    cfg = LANGUAGES[language]

    if cfg["compile"] is None:
        # Interpreted: run directly
        return run_in_container_with_chaos(
            language=language,
            command=cfg["run"](path.name),
            submission_dir=submission_dir,
            profile_name=profile_name,
            timeout=timeout,
        )
    
    binary      = path.stem
    compile_cmd = cfg["compile"]([path.name], binary)

    print(f"Compiling {path.name}...")
    rc, out, err = run_in_container(language, compile_cmd, submission_dir)
    if rc != 0:
        print("Compilation failed")
        if out: print(out)
        if err: print(err)
        sys.exit(1)
    print("Compiled\n")

    try:
        return run_in_container_with_chaos(
            language=language,
            command=cfg["run"](binary),
            submission_dir=submission_dir,
            profile_name=profile_name,
            timeout=timeout,
        )
    finally:
        run_in_container(language, ["rm", "-f", binary], submission_dir)


# ═══════════════════════════════════════════════════════════════════════════════
# Directory path delegates to submission_runner's build system
# ═══════════════════════════════════════════════════════════════════════════════

def _run_directory(
    directory: Path,
    profile_name: str,
    timeout: int,
) -> ChaosRunResult:
    """
    Uses submission_runner's build_submission() to handle Makefiles,
    multi-file projects, dirs.txt, and build scripts, then runs the
    resulting binary under chaos.
    """
    print(f"Building {directory.name}...")
    build_result = build_submission(str(directory))

    if not build_result.success:
        print("Build failed")
        if build_result.stdout: print(build_result.stdout)
        if build_result.stderr: print(build_result.stderr)
        sys.exit(1)

    command      = list(build_result.run_cmd)
    runtime_args = get_args(str(directory))
    if runtime_args:
        command += runtime_args
        print(f"Build succeeded  →  {' '.join(command)} (args from dirs.txt)\n")
    else:
        print(f"Build succeeded  →  {' '.join(command)}\n")

    language = _infer_language(directory)

    try:
        return run_in_container_with_chaos(
            language=language,
            command=command,
            submission_dir=str(directory),
            profile_name=profile_name,
            timeout=timeout,
        )
    finally:
        _cleanup(directory, language)


def _infer_language(directory: Path) -> str:
    """Walk the directory and return the dominant language based on lang_reg extensions."""
    counts   = {lang: 0 for lang in LANGUAGES}
    priority = list(LANGUAGES.keys())
    for f in directory.rglob("*"):
        for lang, cfg in LANGUAGES.items():
            if f.suffix.lower() in cfg["extensions"]:
                counts[lang] += 1
    return max(counts, key=lambda k: (counts[k], priority.index(k)))


def _cleanup(directory: Path, language: str):
    """Run make clean via run_in_container, or note that artifacts may remain."""
    build_system = detect_build_system(str(directory))
    if build_system == "make":
        run_in_container(language, ["make", "clean"], str(directory))
        print("Cleaned build artifacts (make clean)")
    else:
        print("Note: non-make build artifacts may remain in submission dir")


# ═══════════════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════════════

def save_run_report(results: list[ChaosRunResult], base_dir: str = "chaos_reports"):
    from report_format import parse_metrics, generate_feedback
    from analyze import compare_to_baseline, _interpret

    os.makedirs(base_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir   = os.path.join(base_dir, timestamp)
    os.makedirs(run_dir, exist_ok=True)

    # ── Raw output files ──────────────────────────────────────────────────────
    with open(os.path.join(run_dir, "stdout.txt"), "w") as f:
        for r in results:
            f.write(f"=== {r.profile_name} ===\n")
            f.write(r.stdout or "")
            f.write("\n")

    with open(os.path.join(run_dir, "stderr.txt"), "w") as f:
        for r in results:
            f.write(f"=== {r.profile_name} ===\n")
            f.write(r.stderr or "")
            f.write("\n")

    # ── Build profile_data for JSON and comparison ────────────────────────────
    profile_data = []
    metrics_by_profile = {}
    for r in results:
        try:
            metrics = parse_metrics(r.stdout)
        except Exception:
            metrics = {}
        metrics_by_profile[r.profile_name] = metrics
        profile_data.append({
            "profile":      r.profile_name,
            "exit_code":    r.returncode,
            "oom_killed":   r.oom_killed,
            "timed_out":    r.timed_out,
            "wall_time_s":  r.wall_time_s,
            "peak_rss_mb":  r.peak_rss_mb,
            "cpu_peak_pct": r.cpu_peak_pct,
            "cpu_avg_pct":  r.cpu_avg_pct,
            "pids_peak":    r.pids_peak,
            "has_stderr":   bool((r.stderr or "").strip()),
            "events":       [str(e) for e in r.events],
            "metrics":      metrics,
        })

    with open(os.path.join(run_dir, "result.json"), "w") as f:
        json.dump(profile_data, f, indent=2)

    # ── Build comparison deltas ───────────────────────────────────────────────
    try:
        comparisons = compare_to_baseline(profile_data)
        comparison_by_profile = {c["profile"]: c for c in comparisons}
    except Exception:
        comparisons = []
        comparison_by_profile = {}

    # ── Baseline info ─────────────────────────────────────────────────────────
    baseline = next((r for r in results if r.profile_name == "none"), None)
    baseline_wall = baseline.wall_time_s if baseline else 0

    # ── Write single combined report ──────────────────────────────────────────
    lines = []
    bar   = "=" * 56

    lines.append(bar)
    lines.append("  CHAOS TESTING REPORT")
    lines.append(bar)

    if baseline:
        lines.append(f"\n  Baseline (no constraints):")
        lines.append(f"    Wall time : {baseline.wall_time_s:.1f}s")
        lines.append(f"    Memory    : {baseline.peak_rss_mb:.1f} MB")
        lines.append(f"    CPU usage : {baseline.cpu_avg_pct:.1f}% avg")
        lines.append(f"    Exit code : {baseline.returncode}")
        lines.append(f"\n  All other profiles are compared against this baseline.")

    lines.append(f"\n{bar}")
    lines.append("  RESULTS BY PROFILE")
    lines.append(bar)

    for r in results:
        if r.profile_name == "none":
            continue

        metrics  = metrics_by_profile.get(r.profile_name, {})
        feedback = generate_feedback(metrics, r)
        cmp      = comparison_by_profile.get(r.profile_name, {})

        # Status
        if r.oom_killed:
            status = f"FAIL: out of memory ({r.peak_rss_mb:.0f} MB used)"
        elif r.timed_out:
            status = "FAIL: timed out"
        elif r.returncode != 0:
            status = f"FAIL: exit code {r.returncode}"
        elif cmp.get("wall_time_pct") and cmp["wall_time_pct"] > 200:
            status = "FAIL: too slow"
        elif cmp.get("wall_time_pct") and cmp["wall_time_pct"] > 30:
            status = "WARN"
        else:
            status = "PASS"

        lines.append(f"\n  {r.profile_name.upper()}  [{status}]")

        # Wall time with delta
        if cmp and baseline_wall > 0:
            wt_pct = cmp.get("wall_time_pct")
            pct_str = f"  ({wt_pct:+.0f}% vs baseline)" if wt_pct is not None else ""
            lines.append(f"    Wall time : {r.wall_time_s:.1f}s{pct_str}")
        else:
            lines.append(f"    Wall time : {r.wall_time_s:.1f}s")

        lines.append(f"    Exit code : {r.returncode}")

        # Memory
        mem = r.peak_rss_mb if r.peak_rss_mb > 0 else metrics.get("mem_peak", 0)
        if cmp:
            rss_pct = cmp.get("rss_pct")
            pct_str = f"  ({rss_pct:+.0f}% vs baseline)" if rss_pct is not None else ""
            lines.append(f"    Memory    : {mem:.1f} MB{pct_str}")
            if rss_pct is not None and rss_pct > 50:
                lines.append(f"      WARN: Memory usage {rss_pct:.0f}% higher than baseline. "
                            "Check for accumulation under this profile.")
        else:
            lines.append(f"    Memory    : {mem:.1f} MB")

        # CPU
        lines.append(f"    CPU usage : {r.cpu_avg_pct:.1f}% avg  "
                     f"(peak {r.cpu_peak_pct:.1f}%)")

        # Feedback
        if feedback:
            lines.append("    Feedback  :")
            for line in feedback:
                lines.append(f"      {line}")

    # ── Overall verdict ───────────────────────────────────────────────────────
    lines.append(f"\n{bar}")
    lines.append("  OVERALL VERDICT")
    lines.append(bar)

    non_baseline = [r for r in results if r.profile_name != "none"]
    failures = []
    warnings = []
    passing  = []

    for r in non_baseline:
        cmp = comparison_by_profile.get(r.profile_name, {})
        wt  = cmp.get("wall_time_pct") or 0
        if r.oom_killed or r.timed_out or r.returncode != 0 or wt > 200:
            failures.append(r.profile_name)
        elif wt > 30:
            warnings.append(r.profile_name)
        else:
            passing.append(r.profile_name)

    lines.append(f"\n  Profiles tested  : {len(non_baseline)}")
    lines.append(f"  Passing          : {len(passing)}")
    lines.append(f"  Warnings         : {len(warnings)}")
    lines.append(f"  Failing          : {len(failures)}")

    if failures:
        lines.append("\n  Failed under:")
        for name in failures:
            r   = next(x for x in results if x.profile_name == name)
            cmp = comparison_by_profile.get(name, {})
            wt  = cmp.get("wall_time_pct")
            if r.oom_killed:
                reason = "ran out of memory"
            elif r.timed_out:
                reason = "exceeded time limit"
            elif r.returncode != 0:
                reason = f"crashed (exit {r.returncode})"
            else:
                reason = f"ran {wt:.0f}% slower than baseline"
            lines.append(f" {name:<22} {reason}")

    if warnings:
        lines.append("\n  Warnings:")
        for name in warnings:
            cmp = comparison_by_profile.get(name, {})
            wt  = cmp.get("wall_time_pct") or 0
            lines.append(f"WARN: {name:<22} ran {wt:.0f}% slower than baseline")

    if not failures and not warnings:
        lines.append("\n SUCCESS: Your program passed all chaos profiles.")
        lines.append("    It handles resource constraints gracefully.")
    elif not failures:
        lines.append("\n  Your program passed all profiles but showed some slowdown.")
        lines.append("  Consider optimising for resource-constrained environments.")
    else:
        lines.append("\n  Your program failed under some resource constraints.")
        lines.append("  Review the feedback above for each failing profile.")

    lines.append(f"\n{bar}\n")

    with open(os.path.join(run_dir, "report.txt"), "w") as f:
        f.write("\n".join(lines))

    print(f"\nReport saved to: {run_dir}/report.txt")
    return run_dir


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Run a student submission (file or directory) under chaos conditions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Available profiles:\n" + "\n".join(
            f"  {name:<22} {p.description}" for name, p in PROFILES.items()
        ),
    )
    parser.add_argument(
        "--path", required=True,
        help="Path to a submission file (.c, .cpp, .py) or project directory",
    )
    parser.add_argument(
        "--profile", default=None,
        help="Run a single named profile instead of all profiles",
    )
    parser.add_argument(
        "--timeout", type=int, default=120,
        help="Max run time in seconds (default: 120)",
    )
    args = parser.parse_args()

    profiles_to_run = [args.profile] if args.profile else list(PROFILES.keys())

    results = []
    for profile_name in profiles_to_run:
        print(f"\n{'━' * 56}")
        print(f"  Profile: {profile_name}")
        print(f"{'━' * 56}")
        result = run_chaos_on_path(args.path, profile_name, args.timeout)
        result.print_report()
        results.append(result)

    save_run_report(results)


if __name__ == "__main__":
    main()