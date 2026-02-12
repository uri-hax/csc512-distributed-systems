# Submission Runner - Docker Setup

This system runs student code submissions in isolated Docker containers for security and consistency.

## Why Docker?

- **Consistency**: Same environment regardless of host OS
- **Security**: Isolated execution with resource limits
- **Reproducibility**: Identical results across different machines

## Setup

### 1. Install Docker

Make sure Docker is installed and running:
```bash
docker --version
```

### 2. Build Docker Images

Run the setup script to build all language containers:
```bash
python setup_docker.py
```

This creates three Docker images:
- `submission-runner-python` - Python 3.11 environment
- `submission-runner-c` - GCC 13 for C
- `submission-runner-cpp` - GCC 13 for C++

## Resource Limits

Each container has the following limits:
- **Memory**: 512MB
- **CPU**: 1.0 core
- **Network**: Disabled (no internet access)
- **Timeout**: 30 seconds (configurable)
- **User**: Runs as non-root (UID 1000)

## Usage

```bash
python test_harness.py
```


## Customization

### Add Python Packages

Edit `Dockerfile.python` and add packages to the `pip install` line:

```dockerfile
RUN pip install --no-cache-dir numpy pandas matplotlib scipy
```

Then rebuild:
```bash
python setup_docker.py
```

### Adjust Resource Limits

Edit `docker_runner.py` and modify the limits in `run_in_container()`:

```python
"--memory", "1g",      # Increase to 1GB
"--cpus", "2.0",       # Allow 2 CPU cores
```

### Change Timeout

In `run_docker.py`, adjust the `timeout` parameter (default 30 seconds).

## Troubleshooting

### Permission Errors

If you get permission errors, ensure Docker is running and your user has Docker permissions:
```bash
sudo usermod -aG docker $USER
```
Then log out and back in.

### Container Not Found

If you get "image not found" errors, rebuild the images:
```bash
python setup_docker.py
```

### Files Not Visible in Container

Make sure you're passing absolute paths. The `docker_runner.py` handles this automatically.