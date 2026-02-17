# Getting Started

## Quick Start (5 minutes)

### Prerequisites

- Docker (recommended) or Python 3.12+
- Source code repository or Docker image to scan

### Option 1: Docker (Recommended)

```bash
# Build the toolkit image
cd security_toolkit
docker build -t security-toolkit .

# Source mode - scan your code
docker run --rm -v /path/to/your/repo:/workspace \
    security-toolkit scan --target /workspace

# Runtime mode - scan a Docker image
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    --user root security-toolkit inspect --image my-app:latest

# Full mode - source + runtime combined
docker run --rm \
    -v /path/to/your/repo:/workspace \
    -v /var/run/docker.sock:/var/run/docker.sock \
    --user root security-toolkit full \
        --target /workspace \
        --image my-app:latest
```

### Option 2: Local Install

```bash
# Install locally
pip install -e "./security_toolkit[dev]"

# Run scans
security_toolkit scan --target /path/to/repo
security_toolkit inspect --image my-app:latest
security_toolkit full --target ./myapp --image myapp:latest
```

## Understanding Results

### Severity Levels

- **CRITICAL**: Immediate action required (e.g., hard-coded secrets)
- **HIGH**: Strong risk (e.g., unsafe function use, missing auth)
- **MEDIUM**: Moderate risk (e.g., debug mode enabled)
- **LOW**: Minor issues (e.g., missing health check)
- **INFO**: Informational findings

### Output Formats

- **Console**: Rich terminal output (default)
- **JSON**: Machine-readable report (with `--output report.json`)
- **Markdown**: Human-readable report (created automatically with JSON)

## Next Steps

- See [CLI Reference](./cli-reference.md) for all command options
- See [Plugin Development](./plugins/developing.md) to write custom scanners
- See [Deployment Guide](./deployment/) for CI/CD integration
