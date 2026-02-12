from docker_runner import run_in_container
from detect import get_args
import os

def run_submission(build_result, cwd):
    """
    Run a submission in a Docker container.
    Args:
        build_result: BuildResult object containing run command
        cwd: Working directory (submission path)
    Returns:
        tuple: (returncode, stdout, stderr)
    """
    # Get command line arguments from submission config
    args = get_args(cwd)
    
    cmd = build_result.run_cmd[0]
    
    # If running a shell script in a subdirectory
    if cmd.endswith('.sh') and '/' in cmd:
        script_dir = os.path.dirname(cmd)
        script_file = os.path.basename(cmd)
        args_str = ' '.join(args) if args else ''
        run_cmd = ["bash", "-c", f"cd {script_dir} && bash {script_file} {args_str}"]
        language = "c"
    elif cmd.endswith('.sh'):
        script_name = cmd.lstrip('./')
        run_cmd = ["bash", script_name] + args
        language = "c"
    elif "python" in cmd:
        run_cmd = build_result.run_cmd + args
        language = "python"
    else:
        # For compiled binaries (including those from Makefile)
        run_cmd = build_result.run_cmd + args
        
        # Detect language from extension
        if cmd.endswith('.cpp') or 'cpp' in cmd:
            language = "cpp"
        else:
            language = "c"
    
    return run_in_container(language, run_cmd, cwd)