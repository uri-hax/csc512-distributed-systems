from .build_result import BuildResult
from .docker_runner import run_in_container
from .detect import get_build_script, get_output
import os

def build_with_make(submission_dir):
    # Clean first to remove any pre-existing object files
    run_in_container(
        "cpp",
        ["make", "clean"],
        submission_dir
    )
    
    # Now build
    returncode, stdout, stderr = run_in_container(
        "cpp",
        ["make"],
        submission_dir
    )
    
    # Check if OUTPUT was specified in dirs.txt
    output_binary = get_output(submission_dir)
    
    if not output_binary:
        return BuildResult(
            False, 
            None, 
            stdout, 
            stderr + "\nERROR: No OUTPUT specified in dirs.txt. Please add 'OUTPUT: <binary_name>'"
        )
    
    return BuildResult(returncode == 0, [f"./{output_binary}"], stdout, stderr)


def build_with_bash(submission_dir):
    script_name = get_build_script(submission_dir)
    
    if not script_name:
        return BuildResult(False, None, "", "No bash script found")
    
    # Make all .sh files executable first
    run_in_container(
        "c",
        ["bash", "-c", "find . -name '*.sh' -exec chmod +x {} \\;"],
        submission_dir
    )
    
    # Check if script is in a subdirectory
    if '/' in script_name:
        script_dir = os.path.dirname(script_name)
        script_file = os.path.basename(script_name)
        # Change to the script's directory before running
        returncode, stdout, stderr = run_in_container(
            "c",
            ["bash", "-c", f"cd {script_dir} && bash {script_file}"],
            submission_dir
        )
        run_cmd = [f"./{script_name}"]
    else:
        # Script is in root directory
        returncode, stdout, stderr = run_in_container(
            "c",
            ["bash", script_name],
            submission_dir
        )
        run_cmd = [f"./{script_name}"]
    
    return BuildResult(returncode == 0, run_cmd, stdout, stderr)


def default_language_build(submission_dir, sources, cfg):
    # Interpreted language (Python)
    if cfg["compile"] is None:
        entry = sources[0]
        return BuildResult(True, cfg["run"](entry), "", "")
    
    # Compiled language (C/C++)
    binary = "a.out"
    compile_cmd = cfg["compile"](sources, binary)
    
    # Determine language from file extensions
    ext = sources[0].split('.')[-1]
    language = "cpp" if ext == "cpp" else "c"
    
    returncode, stdout, stderr = run_in_container(
        language,
        compile_cmd,
        submission_dir
    )
    
    if returncode != 0:
        return BuildResult(False, None, stdout, stderr)
    
    return BuildResult(True, cfg["run"](binary), stdout, stderr)