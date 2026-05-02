"""
Parse metrics into clean report formatting
"""

import re

def parse_metrics(stdout):
    cpu = []
    mem = []
    io = []
    history_sizes = []

    for line in stdout.splitlines():
        if "[CPU]" in line and "ops/sec" in line:
            m = re.search(r"ops/sec:\s+(\d+)", line)
            if m:
                cpu.append(int(m.group(1)))

        elif "[MEM]" in line:
            m = re.search(r"resident:\s+(\d+)", line)
            if m:
                mem.append(int(m.group(1)))

        elif "[I/O]" in line:
            m = re.search(r"throughput:\s+([\d.]+)", line)
            if m:
                io.append(float(m.group(1)))

        elif "Allocated chunk" in line:
            m = re.search(r"total:\s+(\d+)\s+MB", line)
            if m:
                mem.append(int(m.group(1)))

        elif "iterations/sec:" in line:
            m = re.search(r"iterations/sec:\s+([\d.]+)", line)
            if m:
                cpu.append(float(m.group(1)))

        elif "ERROR:" in line or "Cleanup complete" in line:
            pass

        # track history buffer size over time (growth after a flush is a leak signal)
        if "history=" in line:
            m = re.search(r"history=(\d+)", line)
            if m:
                history_sizes.append(int(m.group(1)))

    # detect flush events: history size drops then climbs again
    flush_detected = False
    if len(history_sizes) > 10:
        for i in range(1, len(history_sizes)):
            if history_sizes[i] < history_sizes[i-1] - 5:
                flush_detected = True
                break

    return {
        "cpu_avg":        sum(cpu) / len(cpu) if cpu else 0,
        "cpu_min":        min(cpu)             if cpu else 0,
        "mem_peak":       max(mem)             if mem else 0,
        "io_avg":         sum(io) / len(io)    if io else 0,
        "io_min":         min(io)              if io else 0,
        "history_sizes":  history_sizes,
        "flush_detected": flush_detected,
    }

def parse_stderr_signals(stderr: str) -> dict:
    """
    Language-agnostic signals from stderr that indicate specific failure modes.
    Is this all-encompassing? Room for refinement
    """
    s = stderr.lower()
    return {
        "heap_corruption": any(x in s for x in [
            "double free", "corrupted", "invalid next size",
            "munmap_chunk", "free(): invalid", "malloc(): corrupted"
        ]),
        "segfault":        "segmentation fault" in s,
        "stack_overflow":  any(x in s for x in [
            "stack overflow", "stack smashing", "segmentation fault"
        ]),
        "python_traceback": "traceback (most recent call last)" in s,
        "memory_error":    any(x in s for x in [
            "memoryerror", "bad_alloc", "cannot allocate"
        ]),
        "assertion":       any(x in s for x in [
            "assertion failed", "assert", "abort"
        ]),
        "timeout_signal":  any(x in s for x in [
            "killed", "timeout", "time limit"
        ]),
    }

def analyze_failure(result):
    """
        Analyzes how a program failed. Only meaningful when returncode != 0.
        Returns a list of observations about the failure mode.
    """
    if result.returncode == 0:
        return []

    observations = []
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()

    # ── Classify failure mode ─────────────────────────────────────────────────
    if result.oom_killed or result.returncode == 137:
        peak = getattr(result, "peak_rss_mb", 0)
        observations.append("FAIL: Your program was killed because it used more "
                        "memory than was available under this profile.")
        if peak > 0:
            observations.append(f"  Peak memory usage was {peak:.0f} MB before the kill.")
        observations.append("  This is not a code bug and it means your program's memory "
                        "requirements exceed the constraint being tested.")
        observations.append("  To handle this gracefully: check allocation return values, "
                        "reduce peak memory usage, or free data structures earlier.")

    elif result.returncode == 139:
        observations.append("FAIL: Segmentation fault (SIGSEGV, exit 139).")
        if "double free" in stderr.lower():
            observations.append("  Likely cause: double free.")
        elif "heap" in stderr.lower():
            observations.append("  Likely cause: heap corruption.")
        else:
            observations.append("  Likely cause: invalid memory access. Check "
                                "pointer arithmetic, buffer bounds, or use-after-free.")

    elif result.returncode == 134:
        observations.append("FAIL: Abort (SIGABRT, exit 134).")
        if "double free" in stderr.lower() or "corrupted" in stderr.lower():
            observations.append("  Likely cause: glibc detected heap corruption "
                                "(double free or buffer overflow).")
        elif "assert" in stderr.lower():
            observations.append("  Likely cause: failed assertion.")
        else:
            observations.append("  Likely cause: uncaught exception or explicit abort().")

    elif result.returncode == 136:
        observations.append("FAIL: Floating point exception (SIGFPE, exit 136).")
        observations.append("  Likely cause: division by zero.")

    elif result.timed_out or result.returncode == 124:
        observations.append("FAIL: Your program did not finish within the time limit.")
        observations.append("  Under reduced CPU this is expected for compute-intensive "
                        "programs. Your program may simply require more CPU than "
                        "was available.")
        observations.append("  If this also happens under the 'none' profile, check "
                        "for infinite loops or deadlocks.")

    else:
        observations.append(f"FAIL: Non-zero exit code {result.returncode}.")

    # ── Graceful error handling check — stderr only, not stdout ──────────────
    error_keywords = ["error", "failed", "errno", "cannot", "unable", "cleanup", "err",
                  "info", "warning", "shutting", "freed", "abort"]
    wrote_to_stderr = bool(stderr)

    if result.oom_killed or result.returncode == 137:
        # SIGKILL cannot be caught and program had no opportunity to write stderr
        observations.append("  NOTE: The program was killed by the OS and had no "
                            "opportunity to write error output or run cleanup code.")
    elif result.returncode in (139,):
        # Segfault also unhandleable
        observations.append("  NOTE: This signal cannot be caught or handled "
                            "by the program.")
    elif wrote_to_stderr:
        observations.append("  GOOD: Program wrote a meaningful error to stderr "
                            "before exiting.")
    else:
        observations.append("  WARN: No error output on stderr before exit.")
        observations.append("  Expected: write to stderr before calling exit(), "
                            "e.g. std::cerr or fprintf(stderr, ...).")
        if stdout and any(w in stdout.lower() for w in error_keywords):
            observations.append("  NOTE: Error message found in stdout "
                                "use stderr for error reporting.")
    # ---- Memory Leak check --------------------------------------------------
    if result.returncode not in (137, 139, 134, 136) and not result.oom_killed:
        if hasattr(result, "peak_rss_mb") and result.peak_rss_mb > 0:
            observations.append(
                f"  WARN: Program used up to {result.peak_rss_mb:.1f} MB RSS and "
                f"exited with code {result.returncode}, verify all allocations "
                "are freed on every exit path."
            )
        if hasattr(result, "peak_rss_mb") and 0 < result.wall_time_s < 30 and result.peak_rss_mb > 0:
            observations.append(
                f"  WARN: Early exit after {result.wall_time_s:.1f}s with "
                f"{result.peak_rss_mb:.1f} MB peak error path may skip cleanup."
            )

    return observations

def generate_feedback(metrics, result):
    feedback = []

    stderr = (result.stderr or "").strip()
    if stderr and result.returncode == 0:
        feedback.append("GOOD: Program wrote diagnostic output to stderr during "
                        "normal operation")
    elif stderr and result.returncode != 0:
        pass  # handled in analyze_failure

    if result.oom_killed:
        feedback.append("FAIL: Your program ran out of memory and was killed.")

    if result.oom_killed:
        feedback.append("FAIL: Your program ran out of memory and was killed.")

    if result.timed_out:
        feedback.append("FAIL: Your program exceeded the time limit under "
                        f"'{result.profile_name}' constraints.")

    if metrics["cpu_min"] < 0.5 * metrics["cpu_avg"] and metrics["cpu_avg"] > 0:
        feedback.append("WARN: CPU throughput dropped more than 50%. Your program "
                        "is sensitive to CPU constraints.")

    cpu_avg  = getattr(result, "cpu_avg_pct", 0)

    # Flag programs that used significant CPU — makes cpu profiles meaningful
    if cpu_avg > 0 and cpu_avg < 20 and "cpu" in result.profile_name:
        feedback.append(f"WARN: CPU usage was only {cpu_avg:.1f}% under "
                        f"'{result.profile_name}'")

    if metrics.get("flush_detected"):
        feedback.append(
            "WARN: Data structure was flushed but memory kept growing "
            "flush may not be freeing heap objects. "
            "If using vector<T*>, delete each element before clear()."
        )

    history_sizes = metrics.get("history_sizes", [])
    if len(history_sizes) > 20 and not metrics.get("flush_detected"):
        if history_sizes[-1] > history_sizes[0] * 2:
            feedback.append(
                f"WARN: Internal buffer grew from {history_sizes[0]} to "
                f"{history_sizes[-1]} entries. Check that old entries are released."
            )

    if getattr(result, "pids_peak", 0) > 20:
        feedback.append(
            f"WARN: Peak thread/process count was {result.pids_peak}. "
            "Ensure all threads are joined before exit."
        )

    failure_analysis = analyze_failure(result)
    if failure_analysis:
        feedback.append("\nFailure Analysis:")
        feedback.extend(failure_analysis)

    if not feedback:
        feedback.append("SUCCESS: Your program handled these conditions well.")

    return feedback