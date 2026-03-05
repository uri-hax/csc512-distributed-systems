# Standalone chaos testing entry point.
# Run directly:
#   python run_chaos.py --file /path/to/submission.ext --profile cpu_gradual
#   python run_chaos.py --file /path/to/submission.ext --all-profiles
#
# Or import into a pipeline:
#   from run_chaos import run_chaos_on_file
#   result = run_chaos_on_file("/path/to/submission.ext", "memory_squeeze", timeout=90)
#   result.print_report()

import argparse
import sys
from pathlib import Path

from chaos_config import PROFILES, get_profile
from chaos_runner import run_in_container_with_chaos, ChaosRunResult

# Maps file extension to your existing Docker image language keys
LANGUAGE_MAP = {
    ".py":  "python",
    ".c":   "c",
    ".cpp": "cpp",
}

COMPILER_MAP = {
    ".c":   ("gcc", "g++")[0],
    ".cpp": "g++",
}


def run_chaos_on_file(
    file_path: str | Path,
    profile_name: str = "none",
    timeout: int = 120,
) -> ChaosRunResult:
    """
    Compile (if needed) and run a single submission file under a chaos profile.

    Args:
        file_path:    Absolute or relative path to the submission file
        profile_name: Name of a chaos profile from chaos_config.PROFILES
        timeout:      Max seconds to allow the run

    Returns:
        ChaosRunResult — call .as_tuple() for (returncode, stdout, stderr)
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Submission file not found: {path}")

    ext = path.suffix.lower()
    language = LANGUAGE_MAP.get(ext)
    if language is None:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {list(LANGUAGE_MAP)}")

    submission_dir = str(path.parent)

    # Python: run directly
    if language == "python":
        return run_in_container_with_chaos(
            language=language,
            command=["python3", path.name],
            submission_dir=submission_dir,
            profile_name=profile_name,
            timeout=timeout,
        )

    # C/C++: compile first, then run under chaos
    from chaos_runner import DOCKER_IMAGES
    import subprocess, os

    compiler = COMPILER_MAP[ext]
    binary   = path.stem
    image    = DOCKER_IMAGES[language]
    abs_dir  = os.path.abspath(submission_dir)

    print(f"Compiling {path.name}...")
    compile_cmd = [
        "docker", "run", "--rm",
        "-v", f"{abs_dir}:/submission",
        "-w", "/submission",
        "--network", "none",
        "--user", "1000:1000",
        image,
        compiler, "-Wall", "-o", binary, path.name,
    ]
    result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print("✗ Compilation failed")
        if result.stdout: print(result.stdout)
        if result.stderr: print(result.stderr)
        sys.exit(1)
    print("✓ Compiled\n")

    try:
        chaos_result = run_in_container_with_chaos(
            language=language,
            command=[f"./{binary}"],
            submission_dir=submission_dir,
            profile_name=profile_name,
            timeout=timeout,
        )
    finally:
        # Clean up compiled binary regardless of outcome
        subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{abs_dir}:/submission", "-w", "/submission",
             "--user", "1000:1000", image,
             "rm", "-f", binary],
            capture_output=True, timeout=10,
        )

    return chaos_result


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run a student submission under chaos conditions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            [f"  {name:<20} {p.description}" for name, p in PROFILES.items()]
        ),
    )
    parser.add_argument("--file",     required=True, help="Path to submission file (.c, .cpp, .py)")
    parser.add_argument("--profile",  default="none", help="Chaos profile name (default: none)")
    parser.add_argument("--timeout",  type=int, default=120, help="Max run time in seconds (default: 120)")
    parser.add_argument("--all-profiles", action="store_true", help="Run every profile and print each report")
    args = parser.parse_args()

    profiles_to_run = list(PROFILES.keys()) if args.all_profiles else [args.profile]

    for profile_name in profiles_to_run:
        if args.all_profiles:
            print(f"\n{'━'*56}")
            print(f"  Profile: {profile_name}")
            print(f"{'━'*56}")
        result = run_chaos_on_file(args.file, profile_name, args.timeout)
        result.print_report()


if __name__ == "__main__":
    main()