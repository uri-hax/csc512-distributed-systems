import subprocess
import os
from pathlib import Path

DOCKER_IMAGES = {
    "python": "submission-runner-python",
    "c": "submission-runner-c",
    "cpp": "submission-runner-cpp"
}

def build_docker_images():
    """Build all Docker images. Run this once during setup."""
    here = Path(__file__).parent
    
    for lang, image_name in DOCKER_IMAGES.items():
        dockerfile = here / f"Dockerfile.{lang}"
        if not dockerfile.exists():
            print(f"Warning: {dockerfile} not found, skipping {lang}")
            continue
        
        print(f"Building Docker image for {lang}...")
        result = subprocess.run(
            ["docker", "build", "-f", str(dockerfile), "-t", image_name, "."],
            cwd=str(here),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"Successfully built {image_name}")
        else:
            print(f"Failed to build {image_name}")
            print(result.stderr)

def run_in_container(language, command, submission_dir, timeout=30):
    """
    Run a command in a Docker container for the specified language.
    
    Args:
        language: "python", "c", or "cpp"
        command: List of command arguments (e.g., ["python3", "main.py"])
        submission_dir: Path to submission directory (will be mounted as /submission)
        timeout: Timeout in seconds (default 30)
    
    Returns:
        tuple: (returncode, stdout, stderr)
    """
    image_name = DOCKER_IMAGES.get(language)
    if not image_name:
        raise ValueError(f"Unsupported language: {language}")
    
    # Convert submission_dir to absolute path
    submission_dir = os.path.abspath(submission_dir)
    
    # Build docker run command
    docker_cmd = [
        "docker", "run",
        "--rm",  # Remove container after execution
        "-v", f"{submission_dir}:/submission",  # Mount submission directory
        "-w", "/submission",  # Set working directory
        "--network", "none",  # Disable network access for now
        "--memory", "512m",  # Limit memory to 512MB
        "--cpus", "1.0",  # Limit to 1 CPU
        "--user", "1000:1000",  # Run as non-root user
        image_name,
        *command
    ]
    
    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Execution timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", f"Docker execution error: {str(e)}"

if __name__ == "__main__":
    # Build all Docker images
    print("Building Docker images...")
    build_docker_images()
    print("\nDone! Images are ready to use.")