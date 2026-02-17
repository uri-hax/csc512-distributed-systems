# CLI Reference

## Commands

### scan -- Static Code Analysis

Analyze source code for vulnerabilities (SAST, SCA, IaC, secrets).

```bash
security_toolkit scan --target <DIR> [OPTIONS]
```

**Examples:**

```bash
# Basic scan
docker run --rm -v /myapp:/workspace security-toolkit scan --target /workspace

# With output report
docker run --rm -v /myapp:/workspace -v $(pwd)/reports:/reports \
    security-toolkit scan \
        --target /workspace \
        --output /reports/report.json

# Strict: fail on any HIGH+ finding
docker run --rm -v /myapp:/workspace security-toolkit scan \
    --target /workspace \
    --fail-on high
```

### inspect -- Runtime Analysis

Analyze running containers or services (memory forensics, DAST, drift detection).

```bash
security_toolkit inspect --image <IMAGE> | --pid <PID> | --url <URL> [OPTIONS]
```

**Examples:**

```bash
# Docker image inspection
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock --user root \
    security-toolkit inspect --image my-app:latest

# Running process inspection (by PID)
security_toolkit inspect --pid 1234

# Live service DAST scanning
docker run --rm --network host security-toolkit inspect \
    --url http://localhost:5000
```

### full -- Combined Analysis

Run both source and runtime analysis in one command.

```bash
security_toolkit full \
    --target <DIR> \
    --image <IMAGE> | --url <URL> \
    [OPTIONS]
```

**Examples:**

```bash
# Source + runtime combined
docker run --rm \
    -v /myapp:/workspace \
    -v /var/run/docker.sock:/var/run/docker.sock \
    --user root security-toolkit full \
        --target /workspace \
        --image my-app:latest \
        --output /tmp/full-report.json
```

## Global Options

| Option              | Description                                             |
| ------------------- | ------------------------------------------------------- |
| `-o, --output PATH` | Write reports to file or directory (JSON + Markdown)    |
| `-u, --url URL`     | URL of running service for DAST (http://localhost:5000) |
| `-w, --workers N`   | Number of parallel plugin workers (default: 4)          |
| `--fail-on LEVEL`   | Exit with code 1 if findings >= level (default: high)   |
| `--include-raw`     | Include raw vendor JSON in reports (verbose)            |
| `-v`                | Verbose logging (-v = INFO, -vv = DEBUG)                |
| `--version`         | Show toolkit version                                    |

## Output

### Report Files

When using `--output`:

- `report.json` - Machine-parseable findings
- `report.md` - Human-readable summary

Files are **timestampless** for CI/CD compatibility.

### Exit Codes

- `0` - Success (findings below threshold)
- `1` - Failure (findings at/above threshold)
- `2` - Error (tool failure)

## CI/CD Integration

### GitHub Actions

```yaml
- name: Security Scan
  run: |
    docker run --rm -v ${{ github.workspace }}:/workspace \
        security-toolkit scan \
            --target /workspace \
            --output /workspace/report.json \
            --fail-on high
```

### GitLab CI

```yaml
security_scan:
  script:
    - docker build -t security-toolkit ./security_toolkit
    - docker run --rm -v $CI_PROJECT_DIR:/workspace \
      security-toolkit scan \
      --target /workspace \
      --output report.json
```

### Jenkins

```groovy
stage('Security Scan') {
    steps {
        sh '''
            docker run --rm -v ${WORKSPACE}:/workspace \
                security-toolkit scan \
                    --target /workspace \
                    --fail-on high
        '''
    }
}
```
