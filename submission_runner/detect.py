import os
from lang_reg import LANGUAGES

def parse_submission_config(submission):
    """
    Parse dirs.txt for file list and arguments.
    Returns: (entry_point, files, args, output_binary)
    """
    config_path = os.path.join(submission, "dirs.txt")
    
    if os.path.exists(config_path):
        path = config_path
    else:
        # No config file - discover files automatically
        files = [f for f in os.listdir(submission)
                if os.path.isfile(os.path.join(submission, f))
                and not f.startswith(".")]
        return None, files, [], None
    
    with open(path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    if not lines:
        return None, [], [], None
    
    # Check for OUTPUT specification
    output_binary = None
    lines_to_remove = []
    
    for i, line in enumerate(lines):
        if line.startswith("OUTPUT:"):
            output_binary = line[7:].strip()
            lines_to_remove.append(i)
            break
    
    # Remove OUTPUT line
    for i in reversed(lines_to_remove):
        lines.pop(i)
    
    # Check if last line is ARGS
    args = []
    if lines and lines[-1].startswith("ARGS:"):
        args_line = lines[-1][5:].strip()
        args = args_line.split() if args_line else []
        lines = lines[:-1]
    
    # Check if first line is an entry point (build script or Makefile)
    entry_point = None
    if lines:
        first_line = lines[0]
        if first_line == "Makefile" or first_line.endswith(".sh"):
            entry_point = first_line
            files = lines[1:]
        else:
            files = lines
    else:
        files = []
    
    return entry_point, files, args, output_binary


def get_files(submission):
    _, files, _, _ = parse_submission_config(submission)
    return files


def get_output(submission):
    """Get output binary name from submission"""
    _, _, _, output = parse_submission_config(submission)
    return output


def get_args(submission):
    """Get CLAs from submission"""
    _, _, args, _ = parse_submission_config(submission)
    return args


def get_build_script(submission):
    """Get the bash script name from config or auto-detect."""
    entry_point, _, _, _ = parse_submission_config(submission)
    
    # If explicitly specified and is a shell script
    if entry_point and entry_point.endswith(".sh"):
        return entry_point
    
    # Auto-detect: look for any .sh file
    sh_files = [f for f in os.listdir(submission) 
                if f.endswith('.sh') and os.path.isfile(os.path.join(submission, f))]
    
    return sh_files[0] if sh_files else None


def detect_language(submission):
    relevant_files = get_files(submission)
    for fname in relevant_files:
        _, ext = os.path.splitext(fname)
        for lang, cfg in LANGUAGES.items():
            if ext in cfg["extensions"]:
                return lang
    raise ValueError("Unsupported language")


def detect_build_system(submission):
    entry_point, _, _, _ = parse_submission_config(submission)
    
    if entry_point:
        if entry_point == "Makefile":
            return "make"
        elif entry_point.endswith(".sh"):
            return "script"
    
    if os.path.exists(os.path.join(submission, "Makefile")):
        return "make"
    
    if get_build_script(submission):
        return "script"
    
    return None