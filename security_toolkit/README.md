## Features

- **SAST**: Static analysis with Semgrep
- **Secret Scanning**: Git history and file scanning with Gitleaks  
- **Dependency Scanning**: Vulnerability detection with Trivy
- **IaC Security**: Terraform config analysis
- **Web Scanning**: OWASP ZAP and Nuclei integration
- **Container Security**: Image and runtime container analysis
- **Drift Detection**: Compare running containers to base images

## Quick Start

### Option 1: Docker (Recommended - All Tools Included)
```bash
# Build image with all scanner tools pre-installed
docker build -t security-toolkit .

# Scan source code
docker run --rm -v /path/to/repo:/workspace security-toolkit scan --target /workspace

# Scan Docker image (requires Docker socket)
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    --user root security-toolkit inspect --image myapp:latest
```

### Option 2: Local Installation
```bash
# Install Python package
pip install -e .

# Install scanner tools (see Dependencies section below)
brew install semgrep gitleaks trivy nuclei

# Run scan
security_toolkit scan --target /path/to/repo
```

## Dependencies

### Python Dependencies
- `rich>=13.0` - Terminal formatting and progress bars

### External Scanner Tools

| Tool | Purpose |
|------|---------|
| **semgrep** | SAST analysis |
| **gitleaks** | Secret scanning |
| **trivy** | Dependency & container scanning |
| **nuclei** | Web vulnerability testing |
| **grype** | Alternative dependency scanner |
| **zap-cli** | OWASP ZAP integration |
| **Docker** | Container operations |

### Minimal Installation (Basic Scanning Only)
```bash
pip install -e .
pip install semgrep
brew install gitleaks trivy
```

### Full Installation (All Tools)
```bash
pip install -e .
brew install semgrep gitleaks trivy nuclei grype zaproxy
brew install --cask docker
```

## Usage

```bash
# Scan source code
security_toolkit scan --target /path/to/repo

# Scan Docker image
security_toolkit inspect --image myapp:latest

# Full scan (source + runtime)
security_toolkit full --target /path/to/repo --image myapp:latest

# Output formats
security_toolkit scan --target /path/to/repo --output report.json
security_toolkit scan --target /path/to/repo --format markdown --output report.md

# Fail on high severity findings
security_toolkit scan --target /path/to/repo --fail-on high
```

Check which tools are available:
```bash
# Check individual tools
semgrep --version
gitleaks version
trivy --version
nuclei -version
docker --version

# Run a scan - it will warn about missing tools
security_toolkit scan --target /path/to/repo
```

## Development

### Install Development Dependencies
```bash
pip install -e ".[dev]"
```

Includes:
- `pytest>=7.0` - Testing framework
- `pytest-cov>=4.0` - Coverage reporting  
- `mypy>=1.0` - Type checking
- `ruff>=0.1` - Linting

### Run Tests
```bash
pytest
pytest --cov=security_toolkit
```

## CI/CD Integration

Use the Docker image for consistent environments:

```yaml
# GitHub Actions
- name: Security Scan
  run: |
    docker build -t security-toolkit .
    docker run --rm -v ${{ github.workspace }}:/workspace \
      security-toolkit scan --target /workspace \
      --fail-on high --output report.json
```

## Requirements

- Python 3.10+
- External scanner tools
- Docker

## License

MIT
