from build import build_submission
from pathlib import Path
from run import run_submission
from docker_runner import run_in_container
from detect import detect_build_system

HERE = Path(__file__).parent
LAB_PATH = HERE.parent / "test_code" / "long_runner.c"

if LAB_PATH.is_file():
    # Handle single file submissions
    SUBMISSION_DIR = LAB_PATH.parent
    print(f"Testing single file: {LAB_PATH.name}")
    print(f"Path: {LAB_PATH}\n")
    
    # Detect language from file extension
    ext = LAB_PATH.suffix.lower()
    
    if ext == '.py':
        # Python: just run it
        returncode, out, err = run_in_container(
            "python",
            ["python3", LAB_PATH.name],
            str(SUBMISSION_DIR)
        )
    elif ext in ['.c', '.cpp']:
        # C/C++: compile first, then run
        language = "cpp" if ext == '.cpp' else "c"
        compiler = "g++" if ext == '.cpp' else "gcc"
        output_binary = LAB_PATH.stem
        
        # Compile
        print(f"Compiling {LAB_PATH.name}...")
        compile_returncode, compile_out, compile_err = run_in_container(
            language,
            [compiler, "-Wall", "-o", output_binary, LAB_PATH.name],
            str(SUBMISSION_DIR)
        )
        
        if compile_returncode != 0:
            print("Compilation failed!")
            print(f"Stdout: {compile_out}")
            print(f"Stderr: {compile_err}")
            exit(1)
        
        print("Compilation successful!\n")
        
        # Run
        returncode, out, err = run_in_container(
            language,
            [f"./{output_binary}"],
            str(SUBMISSION_DIR)
        )
        
        # Cleanup
        run_in_container(
            language,
            ["rm", "-f", output_binary],
            str(SUBMISSION_DIR)
        )
    else:
        print(f"Unsupported file type: {ext}")
        exit(1)
    
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