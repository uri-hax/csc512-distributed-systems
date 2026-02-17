# Security Toolkit

Modular security analysis platform for source code and runtime artifacts.

This is a **self-contained project** following PEP 517 layout -- source code is organized in `src/security_toolkit/`,
with configuration files and documentation at the root. Everything needed to build, run, and extend the
toolkit is included in this repository, including the Dockerfile, docker-compose, and Python packaging.

## Directory Structure

Modern Python project layout (PEP 517) with source code in `src/`:

```
security_toolkit/                        # <-- This is the root. All commands run from here.
|
|-- src/                                 # Source code directory (PEP 517 layout)
|   +-- security_toolkit/                # Main package
|       |-- __init__.py                  # Package root, version
|       |-- __main__.py                  # python -m security_toolkit entry
|       |-- cli.py                       # CLI argument parsing, main()
|       |
|       |-- core/
|       |   |-- models.py                # Finding, ScanReport, NormalizedSeverity, TargetProfile
|       |   |-- plugin.py                # ScannerPlugin ABC + auto-registry metaclass
|       |   |-- profiler.py              # Target detection (languages, IaC, Docker metadata)
|       |   |-- engine.py                # ScanEngine orchestrator (dispatch, dedup, parallel)
|       |   +-- sandbox.py               # Resource limits, isolated Docker networks
|       |
|       |-- scanners/                    # Plugin scanners - organized by concern
|       |   |-- static/                  # Source code analysis
|       |   |   |-- analyzers/
|       |   |   |   └── semgrep.py       # Semgrep with multi-ruleset strategy
|       |   |   |-- secrets/
|       |   |   |   └── gitleaks.py      # Gitleaks Git history secret scanning
|       |   |   |-- dependencies/
|       |   |   |   └── trivy.py         # Trivy filesystem mode for dependency CVEs
|       |   |   └── iac/
|       |   |       └── config.py        # Trivy misconfig scanner
|       |   |
|       |   └-- dynamic/                 # Runtime analysis
|       |       |-- vulnerabilities/
|       |       |   └── container.py     # Trivy image vulnerability scan
|       |       |-- forensics/
|       |       |   ├── memory.py        # Memory dump, secret harvesting, entropy analysis
|       |       |   └── drift.py         # Container filesystem drift detection
|       |       └-- testing/
|       |           ├── http_fuzzer.py   # Nuclei DAST web scanner
|       |           ├── zap.py           # OWASP ZAP active/passive web scanner
|       |           ├── load_tester.py   # Concurrent request testing for race conditions
|       |           ├── resource_monitor.py # Memory leak & connection leak detection
|       |           └── custom_detectors.py # Debug mode, secret endpoints, timing attacks
|       |
|       |-- reporting/
|       |   |-- json_report.py           # Human-readable JSON report (grouped by category)
|       |   |-- markdown_report.py       # Human-readable Markdown report with tables
|       |   +-- console_report.py        # Rich-text terminal rendering
|       |
|       +-- utils/
|           |-- docker_utils.py          # Docker CLI helpers (inspect, pull, exec)
|           +-- process_utils.py         # PID inspection, tool availability checks
|
|-- Dockerfile                           # Multi-stage build with all scanners bundled
|-- docker-compose.yml                   # Convenience services for source & runtime scans
|-- .dockerignore                        # Clean build context
|-- pyproject.toml                       # Python packaging, tool config
|-- __main__.py                          # Development entry point (adds src/ to sys.path)
|-- README.md                            # This file
+-- requirements.txt                     # Runtime dependencies
```

## Key Design Decisions

| Decision                              | Rationale                                                                                                                                                                                         |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **No-build philosophy**               | Analyses source files and pre-built artifacts without compiling -- avoids supply-chain risks.                                                                                                     |
| **Plugin auto-registration**          | A metaclass on `ScannerPlugin` records every concrete subclass at import time. Zero core changes to add new scanners.                                                                             |
| **Thread-based parallelism**          | Plugins shell out to external tools (I/O-bound). `ThreadPoolExecutor` gives concurrency without serialisation overhead.                                                                           |
| **Severity normalisation**            | Every tool uses different labels. A unified 1-5 `NormalizedSeverity` enum makes cross-tool comparison and CI gating trivial.                                                                      |
| **Fingerprint deduplication**         | Overlapping Semgrep rulesets produce duplicate findings. SHA-256 fingerprints over `(rule_id, file, line, title)` collapse them.                                                                  |
| **Sandbox isolation**                 | Runtime scans launch containers with CPU/memory/PID limits + `no-new-privileges` + `CAP_DROP ALL`. Privileged access (SYS_PTRACE) can be enabled for memory forensics.                            |
| **Health check robustness**           | HTTP health checks accept any response (2xx, 4xx, 5xx) to detect running services, not just successful responses.                                                                                 |
| **Port publishing on Docker Desktop** | All runtime plugins use the default Docker bridge network to support port publishing on Docker Desktop and other Docker variants.                                                                 |
| **Docker-first deployment**           | All external tools (Semgrep, Trivy, Nuclei) are bundled in the Docker image. Plugins require their respective tools and skip cleanly if unavailable.                                              |
| **Full mode**                         | The `full` command runs both SOURCE and RUNTIME analysis in one invocation, merging findings into a single report.                                                                                |
| **`--url` direct scanning**           | HTTP-based runtime plugins (DAST, ZAP, load-tester, custom-detectors, resource-monitor) can scan a live service directly via `--url`, bypassing Docker-to-Docker networking limitations.          |
| **Directory output**                  | Use `--output /path/to/directory/` to generate reports in a directory. Creates predictable `report.json` and `report.md` with no timestamps.                                                      |
| **False-positive reduction**          | Semgrep findings from known-noisy rules (e.g. `dynamic-urllib-use-detected`) in internal/tool code paths are auto-consolidated into a single INFO advisory instead of N separate MEDIUM findings. |

## Quick Start

### Option 1: Run via Docker

The Docker image bundles **all** scanner dependencies (Semgrep, Trivy, Nuclei, Gitleaks)
so nothing else needs to be installed on the host. OWASP ZAP runs via its official Docker
image, pulled automatically at runtime.

```bash
# 1. cd into the toolkit folder
cd security_toolkit

# 2. Build the image
docker build -t security-toolkit .

# 3. Source mode -- scan any repo by mounting it as /workspace
docker run --rm -v /path/to/your/repo:/workspace \
    security-toolkit scan --target /workspace

# 4. Save the JSON and Markdown reports to a directory
docker run --rm \
    -v /path/to/your/repo:/workspace \
    -v $(pwd)/reports:/reports \
    security-toolkit scan --target /workspace --output /reports

# 5. Runtime mode -- scan a Docker image (mount the Docker socket)
docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    --user root \
    security-toolkit inspect --image my-app:latest --output /reports/report.json

# 6. Full mode -- combined source + runtime scan (single merged report)
docker run --rm \
    -v /path/to/your/repo:/workspace \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v $(pwd)/reports:/reports \
    --user root \
    security-toolkit full \
        --target /workspace \
        --image my-app:latest \
        --output /reports/full-report.json

# 7. Full mode with --url -- scan a live service directly
#    Start your app first (e.g. python app.py), then:
docker run --rm \
    -v /path/to/your/repo:/workspace \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v $(pwd)/reports:/reports \
    --add-host host.docker.internal:host-gateway \
    --user root \
    security-toolkit full \
        --target /workspace \
        --image my-app:latest \
        --url http://host.docker.internal:5000 \
        --output /reports/full-report.json
```

### Option 2: Docker Compose

```bash
cd security_toolkit

# Source scan -- point SCAN_TARGET at any directory
SCAN_TARGET=/path/to/repo docker compose run --rm source-scan

# Runtime scan -- set the IMAGE variable
IMAGE=my-app:latest docker compose run --rm runtime-scan

# Reports are written to ./reports/
```

### Option 3: Install locally (without Docker)

```bash
# From the parent directory of security_toolkit/
pip install ./security_toolkit

# Or for development with editable install
pip install -e "./security_toolkit[dev]"

# Then run from anywhere
security_toolkit scan --target /path/to/repo
security_toolkit inspect --image my-app:latest

# Scan a running service directly (no Docker networking issues)
security_toolkit inspect --url http://localhost:5000

# Full mode with --url for maximum coverage
security_toolkit full --target ./my-app --image my-app:latest --url http://localhost:5000
```

## CLI Reference

```
security_toolkit scan --target <DIR> [OPTIONS]
security_toolkit inspect --image <IMAGE> [OPTIONS]
security_toolkit inspect --pid <PID> [OPTIONS]
security_toolkit inspect --url <URL> [OPTIONS]
security_toolkit full --target <DIR> --image <IMAGE> [OPTIONS]
security_toolkit full --target <DIR> --url <URL> [OPTIONS]
security_toolkit full --target <DIR> --image <IMAGE> --url <URL> [OPTIONS]

Options:
  --output, -o PATH        Write JSON + Markdown reports to PATH
                           - Directory: creates report.json + report.md in directory
                           - File: creates report.json + report.md with that stem
                           - No timestamp, predictable for CI/CD integration
  --url, -u URL            URL of a running service for direct HTTP scanning
                           Can be combined with --image for Docker-specific plugins
  --fail-on SEVERITY       Exit code 1 if findings >= this level (default: high)
                           Choices: critical, high, medium, low, info
  --workers, -w N          Parallel plugin workers (default: 4)
  --include-raw            Include raw vendor JSON in report (off by default)
  -v                       Verbose logging (-v = INFO, -vv = DEBUG)
```

The `--url` option enables HTTP-based runtime plugins (DAST, ZAP, load-tester,
custom-detectors, resource-monitor) to connect directly to a running service
instead of starting their own Docker container. This bypasses Docker-to-Docker
networking limitations and enables full DAST coverage.

The `full` command runs both source analysis (SAST, SCA, IaC, secret scanning) and runtime
analysis (container scan, memory forensics, DAST via Nuclei and OWASP ZAP, drift detection,
load testing, resource monitoring, custom detectors) in a single invocation, producing one
merged JSON and one merged Markdown report.

### Supported Languages (Source Mode)

The profiler detects and enables language-specific Semgrep rulesets for:

Python, JavaScript, TypeScript, Go, Rust, C, C++, Java, Ruby, PHP, C#,
Kotlin, Scala, Swift, Bash/Shell, Dart, Elixir, Haskell, Lua, Perl, R,
Objective-C, PowerShell, Groovy, Terraform

## Report Format

The toolkit generates **two** human-readable reports:

### JSON Report

Designed to be machine-parseable and human-readable. Findings are grouped by category
(sast, secrets, sca, iac, memory, dast, race-condition, resource-leak, custom) with a clear
severity summary at the top. Raw vendor blobs are **excluded by default** to keep the
report clean -- pass `--include-raw` to add them.

```json
{
  "report": {
    "target": "/workspace/my-repo",
    "mode": "source",
    "started_at": "2025-02-11T12:00:00+00:00",
    "finished_at": "2025-02-11T12:01:30+00:00",
    "verdict": "FAIL"
  },
  "summary": {
    "total_findings": 5,
    "by_severity": {
      "CRITICAL": 0,
      "HIGH": 1,
      "MEDIUM": 3,
      "LOW": 1,
      "INFO": 0
    }
  },
  "findings_by_category": {
    "sast": [
      {
        "severity": "HIGH",
        "tool": "semgrep",
        "rule_id": "python.lang.security.audit.eval-detected",
        "category": "sast",
        "title": "Use of eval() detected",
        "description": "Calling eval() with user input is dangerous ...",
        "location": "src/app.py:42",
        "fingerprint": "a1b2c3d4e5f6g7h8"
      }
    ],
    "sca": [
      {
        "severity": "MEDIUM",
        "tool": "trivy",
        "rule_id": "CVE-2024-1234",
        "category": "sca",
        "title": "requests 2.28.0: CVE-2024-1234",
        "description": "HTTP request smuggling via ...",
        "location": "requirements.txt",
        "fingerprint": "b2c3d4e5f6g7h8i9"
      }
    ]
  },
  "errors": []
}
```

### Markdown Report

A detailed, human-friendly report with:

- Summary table (target, mode, timestamps, verdict)
- Severity breakdown table
- Findings grouped by category with full details
- Optional raw vendor data in collapsible sections
- Timestamped filename: `security_report_YYYYMMDD_HHMMSS.md`

Reports are written side-by-side: `report.json` and `report.md`.

## CI/CD Integration

### CI gate with exit code

```bash
# Fails (exit 1) if any HIGH or CRITICAL finding exists (default)
docker run --rm -v /path/to/repo:/workspace \
    security-toolkit scan --target /workspace --fail-on high

# Only fail on CRITICAL
docker run --rm -v /path/to/repo:/workspace \
    security-toolkit scan --target /workspace --fail-on critical
```

### GitHub Actions

```yaml
name: Security Scan
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build security toolkit
        run: docker build -t security-toolkit ./security_toolkit

      - name: Run source scan
        run: |
          docker run --rm \
            -v ${{ github.workspace }}:/workspace \
            security-toolkit scan \
              --target /workspace \
              --output /workspace/security-report.json \
              --fail-on high

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: security-report
          path: security-report.json
```

### GitLab CI

```yaml
security-scan:
  stage: test
  image: docker:24
  services:
    - docker:24-dind
  variables:
    DOCKER_TLS_CERTDIR: ''
  script:
    - docker build -t security-toolkit ./security_toolkit
    - docker run --rm
      -v "$CI_PROJECT_DIR":/workspace
      security-toolkit scan
      --target /workspace
      --output /workspace/security-report.json
      --fail-on high
  artifacts:
    when: always
    paths:
      - security-report.json
```

## Extending -- Adding a New Plugin

1. Create a new file under `plugins/<category>/`.
2. Subclass `ScannerPlugin` and set `name` and `scan_modes`.
3. Implement `can_handle()` and `execute()`.
4. The plugin auto-registers -- no core code changes needed.

```python
from security_toolkit.core.plugin import ScannerPlugin
from security_toolkit.core.models import Finding, ScanMode, TargetProfile

class MyCustomScanner(ScannerPlugin):
    name = "my-scanner"
    scan_modes = {ScanMode.SOURCE}

    def can_handle(self, profile: TargetProfile) -> bool:
        return "python" in profile.languages

    def execute(self, profile: TargetProfile) -> list[Finding]:
        # Your analysis logic here
        return []
```

## External Tool Dependencies

All tools are **bundled in the Docker image**. For local installs, install them separately:

| Tool                                          | Purpose                                      | Required?                                         |
| --------------------------------------------- | -------------------------------------------- | ------------------------------------------------- |
| [Semgrep](https://semgrep.dev/)               | SAST code scanning                           | Required for SAST plugin                          |
| [Gitleaks](https://gitleaks.io/)              | Git secret scanning (history + working tree) | Required for secret scanning plugin               |
| [Trivy](https://trivy.dev/)                   | SCA, IaC, container scanning                 | Required for SCA, IaC, and container scan plugins |
| [Nuclei](https://nuclei.projectdiscovery.io/) | DAST web scanning (template-based)           | Required for Nuclei DAST plugin                   |
| [OWASP ZAP](https://www.zaproxy.org/)         | DAST web scanning (active/passive proxy)     | Uses ZAP Docker image; pulled automatically       |
| [Docker](https://www.docker.com/)             | Runtime mode operations                      | Required for runtime mode only                    |

### Python Dependencies

Runtime: see `requirements.txt` (rich>=13.0)
Development: see `requirements-dev.txt` (pytest, mypy, ruff)
