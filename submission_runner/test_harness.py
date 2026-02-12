from build import build_submission
from pathlib import Path
from run import run_submission
from docker_runner import run_in_container
from detect import detect_build_system

HERE = Path(__file__).parent
LAB_PATH = HERE.parent / "test_code" / "python_test" / "fibNR.py"

if LAB_PATH.is_file():
    # Create temporary structure
    SUBMISSION_DIR = LAB_PATH.parent
    print(f"Testing single file: {LAB_PATH.name}")
    print(f"Path: {LAB_PATH}\n")
    
    # For single Python files, just run them directly
    returncode, out, err = run_in_container(
        "python",
        ["python3", LAB_PATH.name],
        str(SUBMISSION_DIR)
    )
    print(f"Exit Code: {returncode}")
    if out:
        print(f"Program Output:\n{out}")
    if err:
        print(f"Program Errors:\n{err}")
    exit(0)

# Check if lab directory exists
if not LAB_PATH.exists():
    print(f"ERROR: Directory does not exist: {LAB_PATH}")
    exit(1)

print(f"Testing: {LAB_PATH.name}")
print(f"Path: {LAB_PATH}\n")

try:
    # Build the submission
    result = build_submission(str(LAB_PATH))

    print(f"Build success: {result.success}")
    print(f"Run Command: {result.run_cmd}")
    if result.stdout:
        print(f"Build Stdout: {result.stdout}")
    if result.stderr:
        print(f"Build Stderr: {result.stderr}")

    # Run if build succeeded
    if result.success and result.run_cmd:
        print(f"\n==== Running {LAB_PATH.name} ======")
        returncode, out, err = run_submission(result, str(LAB_PATH))
        print(f"Exit Code: {returncode}")
        if out:
            print(f"Program Output:\n{out}")
        if err:
            print(f"Program Errors:\n{err}")
        
        if returncode == 0:
            print(f"\nIf the program created output files, check: {LAB_PATH}")
    else:
        print("Build failed or no run command - skipping execution")

finally:
    # Clean up build artifacts
    print(f"\n==== Cleaning up ======")
    build_system = detect_build_system(str(LAB_PATH))
    
    if build_system == "make":
        run_in_container("cpp", ["make", "clean"], str(LAB_PATH))
        print("Cleaned build artifacts (make clean)")
    elif build_system == "script":
        # Bash scripts might not have clean targets
        print("Note: Bash build scripts may leave artifacts")
    
    print("Done!")