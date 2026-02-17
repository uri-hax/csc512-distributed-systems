# Security Toolkit: Architecture and Design

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Core Architectural Concepts](#core-architectural-concepts)
3. [Design Philosophy](#design-philosophy)
4. [Complete System Architecture](#complete-system-architecture)
5. [Component Deep Dive](#component-deep-dive)
6. [Data Flow and Orchestration](#data-flow-and-orchestration)
7. [Plugin Architecture](#plugin-architecture-metaclass-pattern)
8. [Key Design Choices](#key-design-choices)
9. [Security Scanning Fundamentals](#security-scanning-fundamentals)
10. [Theoretical Procedures](#theoretical-procedures)
11. [False-Positive Reduction](#false-positive-reduction)
12. [Direct URL Scanning](#direct-url-scanning---url-mode)

---

## Executive Summary

The Security Toolkit is a **modular security analysis platform** designed to perform comprehensive security scanning on source code and runtime artifacts. It operates in three modes:

- **Source Mode**: Static analysis of source code repositories
- **Runtime Mode**: Dynamic analysis of running containers and processes
- **Full Mode**: Combined source + runtime analysis with a single merged report

The toolkit achieves production-readiness through:

- **Plugin-based architecture** with automatic registration (no core code changes needed to add scanners)
- **Severity normalization** across heterogeneous third-party tools
- **Deduplication** to eliminate false positives from overlapping rulesets
- **Sandboxed execution** for safe runtime scanning
- **Unified reporting** in human-readable JSON format

---

## Core Architectural Concepts

### 1. **Plugin-Based Extensibility**

**Concept**: Instead of hardcoding scanner integrations into the core, we use a plugin pattern where each scanner is a self-contained module that implements a well-defined interface.

**Why?**

- **Separation of Concerns**: Each plugin is responsible only for its own tool integration
- **Zero Core Changes**: Adding a new scanner requires only adding a new plugin file—no modifications to the orchestrator
- **Parallel Development**: Multiple teams can develop plugins independently
- **Runtime Discovery**: Plugins auto-register via a metaclass, enabling dynamic discovery

**How It Works**:

```
src/security_toolkit/
├── core/
│   ├── plugin.py          ← Defines ScannerPlugin ABC and _PluginRegistry metaclass
│   └── engine.py          ← Uses plugin registry to discover and instantiate plugins
│
└── scanners/
    ├── static/            ← Source code analysis plugins
    │   ├── analyzers/
    │   │   └── semgrep.py           ← Plugin 1: Semgrep multi-ruleset SAST
    │   ├── secrets/
    │   │   └── gitleaks.py          ← Plugin 2: Gitleaks Git secret scanning
    │   ├── dependencies/
    │   │   └── trivy.py             ← Plugin 3: Trivy SCA dependency scanning
    │   └── iac/
    │       └── config.py            ← Plugin 4: Trivy IaC misconfiguration
    └── dynamic/           ← Runtime analysis plugins
        ├── vulnerabilities/
        │   └── container.py         ← Plugin 7: Trivy container image scan
        ├── forensics/
        │   ├── memory.py            ← Plugin 8: Process memory secret extraction
        │   └── drift.py             ← Plugin 9: Container filesystem drift
        └── testing/
            ├── http_fuzzer.py       ← Plugin 5: Nuclei template-based DAST
            ├── zap.py               ← Plugin 6: OWASP ZAP active/passive DAST
            ├── load_tester.py       ← Plugin 10: Race condition detection
            ├── resource_monitor.py  ← Plugin 11: Memory/connection leak detection
            └── custom_detectors.py  ← Plugin 12: Debug endpoints, timing attacks
```

### 2. **Severity Normalization**

**Concept**: Different security tools (Semgrep, Trivy, Nuclei, ZAP, Gitleaks) use different severity labels. We map all of them to a unified 1–5 scale.

**Why?**

- **Cross-Tool Comparison**: Can't compare findings when Semgrep says "ERROR", Trivy says "CRITICAL", and Nuclei says "HIGH"
- **CI/CD Gates**: Need a consistent threshold to fail builds (e.g., "fail if any HIGH+ finding exists")
- **Reporting Consistency**: JSON reports group by severity, not by tool label

**The Scale**:

```
NormalizedSeverity (IntEnum):
  INFO     = 1
  LOW      = 2
  MEDIUM   = 3
  HIGH     = 4
  CRITICAL = 5
```

**Mapping Example**:

```python
Semgrep "ERROR" → HIGH (4)
Trivy "CRITICAL" → CRITICAL (5)
Nuclei "informative" → INFO (1)
```

### 3. **Fingerprint-Based Deduplication**

**Concept**: When multiple rulesets overlap (e.g., Semgrep's "security-audit" and "owasp-top-ten" rulesets both detect XSS), we compute a SHA-256 fingerprint over `(rule_id, file_path, line, title)` and keep only the highest-severity occurrence.

**Why?**

- **Redundancy Elimination**: Without deduplication, the same vulnerability appears multiple times
- **Noise Reduction**: Makes reports clearer and easier to action
- **Consistent Results**: Fingerprinting ensures the same finding always gets the same hash

**Example**:

```
Finding 1: Semgrep rule=XSS-001, file=/app.py, line=42, title="XSS in user input"
Finding 2: Semgrep rule=XSS-002, file=/app.py, line=42, title="XSS in user input"

Fingerprint 1: SHA256("XSS-001|/app.py|42|XSS in user input")[:16]
Fingerprint 2: SHA256("XSS-002|/app.py|42|XSS in user input")[:16]

If Finding 2 has higher severity, keep Finding 2; discard Finding 1.
```

### 4. **Dual-Mode Scanning**

**Concept**: The toolkit supports three scan modes, each with its own set of applicable plugins.

**Source Mode** (Static Analysis):

- Scans the actual source code files
- Plugins: SAST (Semgrep), Secret Scanning (Gitleaks), SCA (Trivy filesystem), IaC (Trivy misconfig)
- Use case: CI/CD pipeline before deployment, pre-commit hooks, security code reviews

**Runtime Mode** (Dynamic Analysis):

- Scans running containers or processes
- Plugins: Container image vulnerability scan, Memory forensics, Drift detection, DAST (Nuclei + OWASP ZAP), Load testing, Resource monitoring, Custom detectors
- Use case: Post-deployment verification, container security audits, incident response

**Full Mode** (Combined):

- Runs both Source and Runtime analysis in a single invocation
- Merges findings into one unified report with mode="full"
- Use case: Complete security assessment combining static and dynamic analysis

---

## Design Philosophy

### Core Principles

#### **1. No-Build Philosophy**

**Principle**: Analyze source files and pre-built artifacts without compiling.

**Why?**

- **Supply Chain Risk Mitigation**: Compilation requires dependencies and build tools. Those dependencies can be compromised (SolarWinds, Codecov, etc.)
- **Simplicity**: No need for language-specific compilers (Go toolchain, Rust cargo, Python wheels)
- **Speed**: Analysis is faster because there's no build step
- **Universality**: Works on any language without special setup

**Implication**:

- We rely on AST-based code scanning (Semgrep) and static file analysis (Trivy)
- We don't attempt to detect vulnerabilities through runtime behavior unless it's a dynamic tool (DAST)

#### **2. Tool Agnosticism**

**Principle**: The toolkit is a orchestrator over _existing_ security tools, not a replacement for them.

**Why?**

- **Best-of-Breed**: Each tool excels in its domain (Semgrep for code patterns, Trivy for dependencies, Nuclei for web vulnerabilities)
- **Maintainability**: We don't maintain the scanner logic; we focus on orchestration and reporting
- **Community**: Leverage the community investments in tools like Semgrep, Trivy, and Nuclei

**Implication**:

- Each plugin shells out to an external tool via subprocess
- If a tool is missing, the plugin gracefully skips (no hard failure)
- CLI output from tools is parsed in JSON format for consistency

#### **3. Docker-First Deployment**

**Principle**: All external tools (Semgrep, Trivy, Nuclei) are bundled in the Docker image. Plugins require their respective tools and skip cleanly if unavailable via `can_handle()`.

**Example**:

```python
class SemgrepScanner(ScannerPlugin):
    def can_handle(self, profile: TargetProfile) -> bool:
        return check_tool_available("semgrep")

    def execute(self, profile: TargetProfile) -> list[Finding]:
        # Run semgrep via subprocess
        ...
```

If `semgrep` is not installed:

- `can_handle()` returns `False`
- ScanEngine skips this plugin
- Other plugins still run
- No built-in fallbacks -- external tools are always available in the Docker image

#### **4. Configuration Over Code**

**Principle**: Scanner behavior is configured via command-line flags and environment variables, not hardcoded.

**Examples**:

- `--workers N`: Number of parallel plugins
- `--fail-on SEVERITY`: Exit code threshold
- `--include-raw`: Include vendor JSON in reports
- `--url URL`: Direct HTTP scanning of a live service (bypasses Docker networking)
- Environment variables for Docker socket path, Nuclei config directory, etc.

---

## Complete System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLI Entry Point                               │
│  (scan --target /path | inspect --image image | --pid PID |          │
│   inspect --url URL | full --target /path --image image --url URL)    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │  Target Profiler               │
        │  ─────────────────             │
        │  • Detect languages            │
        │  • Find IaC files              │
        │  • Inspect Docker metadata     │
        │  • Gather system info          │
        └────────┬──────────────────────┘
                 │
                 ▼
        ┌────────────────────────────────┐
        │  ScanEngine Orchestrator       │
        │  ─────────────────             │
        │  • Discover plugins            │
        │  • Filter by scan mode         │
        │  • Execute in parallel         │
        │  • Deduplicate findings        │
        └────────┬──────────────────────┘
                 │
        ┌───────────────────┬──────────────────────┬─────────────────┬──────────────────────────────┬────────────────────────┐
        │                   │                      │                 │                              │                        │
        ▼                   ▼                      ▼                 ▼                              ▼                        ▼
    ┌───────────────────┐ ┌──────────────────┐ ┌─────────────────┐ ┌────────────────────────────┐ ┌──────────────────────────┐
    │ Static            │ │ Software         │ │Infrastructure- │ │ Dynamic Application        │ │ Memory Forensics Scanner │
    │ Application       │ │ Composition      │ │ as-Code         │ │ Security Testing           │ │ (Docker process memory   │
    │ Security Testing  │ │ Analysis         │ │ Configuration   │ │ (Nuclei + OWASP ZAP)       │ │  + entropy analysis)     │
    │ (Semgrep)         │ │ (Trivy Filesystem│ │ (Trivy Misconfig)    │                            │                          │
    └───────────────────┘ └──────────────────┘ └─────────────────┘ └────────────────────────────┘ ├──────────────────────────┤
                                                                                                    │ Drift Detector Scanner   │
                                                                                                    │ (Container filesystem   │
                                                                                                    │  diff detection)         │
                                                                                                    ├──────────────────────────┤
                                                                                                    │ Container Image Scanner  │
                                                                                                    │ (Trivy image scan)       │
                                                                                                    ├──────────────────────────┤
                                                                                                    │ Load Tester              │
                                                                                                    │ (Race condition + rate   │
                                                                                                    │  limit detection)        │
                                                                                                    ├──────────────────────────┤
                                                                                                    │ Resource Monitor         │
                                                                                                    │ (Memory & connection     │
                                                                                                    │  leak detection)         │
                                                                                                    ├──────────────────────────┤
                                                                                                    │ Custom Detectors         │
                                                                                                    │ (Debug endpoints,        │
                                                                                                    │  secrets, timing attacks)│
                                                                                                    ├──────────────────────────┤
                                                                                                    │ Gitleaks Scanner         │
                                                                                                    │ (Git secret scanning)    │
                                                                                                    └──────────────────────────┘
        │                   │                      │                 │                              │
        └───────────────────┴──────────────────────┴─────────────────┴──────────────────────────────┘
                                                   │
                                                   ▼
        ┌────────────────────────────────┐
        │  Reporting Engine              │
        │  ─────────────────             │
        │  • Aggregate findings          │
        │  • Compute verdict             │
        │  • Group by category           │
        │  • Normalize severity          │
        └────────┬──────────────────────┘
                 │
        ┌────────┴──────────┐
        │                   │
        ▼                   ▼
    ┌──────────┐      ┌──────────────┐
    │JSON File │      │Rich Console  │
    │(structured)     │(human-friendly)
    └──────────┘      └──────────────┘
```

### Data Flow (Detailed)

```
User Input (CLI)
     │
     ├─ Target: /path/to/repo
     ├─ Mode: scan (source) or inspect (runtime) or full (combined)
     └─ Options: --output, --fail-on, --workers, --include-raw, --url
                 │
                 ▼
          Profile Target
          ├─ Languages: [python, go, c]
          ├─ IaC: has_docker=True, has_k8s=False
          ├─ Path: /path/to/repo
          └─ Metadata: {...}
                 │
                 ▼
          Select Plugins by Mode
          ├─ SOURCE mode → [SastPlugin, ScaPlugin, IacPlugin]
          ├─ RUNTIME mode → [ContainerScanner, MemoryForensics, DriftDetector, DAST, ...]
          ├─ FULL mode → runs SOURCE first, then RUNTIME, merges results
                 │
                 ▼
          For Each Applicable Plugin:
          ├─ Call can_handle(profile)
          │   └─ If False → Skip plugin
          │   └─ If True → Add to execution queue
                 │
                 ▼
          ThreadPoolExecutor (N workers)
          ├─ Plugin 1: semgrep_scanner.execute()
          │   └─ Returns: [Finding(...), Finding(...), ...]
          │
          ├─ Plugin 2: trivy_sca.execute()
          │   └─ Returns: [Finding(...), Finding(...), ...]
          │
          ├─ Plugin 3: config_scanner.execute()
          │   └─ Returns: [Finding(...), Finding(...), ...]
          │
          └─ ... (all in parallel)
                 │
                 ▼
          Aggregate Findings
          └─ List[Finding] with all results
                 │
                 ▼
          Deduplicate by Fingerprint
          ├─ Group findings by fingerprint
          ├─ Keep highest-severity per fingerprint
          └─ Result: deduplicated List[Finding]
                 │
                 ▼
          Normalize and Sort
          ├─ Ensure all severities are NormalizedSeverity enum
          ├─ Sort by severity (descending)
          └─ Result: ready-to-report findings
                 │
                 ▼
          Compute Report Metadata
          ├─ Target, Mode, Timestamps
          ├─ Verdict: PASS/WARN/FAIL based on severities
          ├─ Severity counts
          └─ Errors (if any tool failed)
                 │
                 ▼
          Generate Reports
          ├─ Console Output (Rich table + colored text)
          └─ JSON File (if --output specified)
                 │
                 ▼
          Exit Code Logic
          ├─ If any finding.severity >= fail_threshold → exit(1)
          └─ Else → exit(0)
```

---

## Component Deep Dive

### 1. **Target Profiler** (`core/profiler.py`)

**Responsibility**: Determine what's being scanned and gather metadata for plugin selection.

**Why Profiling?**

- **Plugin Selection**: Some plugins only apply to certain languages or artifact types
- **Metadata for Scanners**: Plugins need to know about the environment (e.g., Dockerfile presence for IaC plugins)
- **Mode Detection**: Distinguish between source and runtime scanning

**How It Works**:

```python
def profile_target(
    target: str | None = None,
    image: str | None = None,
    pid: int | None = None,
    url: str | None = None
) -> TargetProfile:
    """
    Determine scan mode and gather metadata.
    url can be combined with image for maximum coverage.
    """
```

**For Source Mode** (directory):

1. **Language Detection** via file signatures (25+ languages supported):
   - `.py` files -> Python
   - `.go` files -> Go
   - `.rs` files -> Rust
   - `.c/.h` files -> C
   - `.kt/.kts` files -> Kotlin
   - `.sh/.bash` files -> Bash
   - `.swift` files -> Swift
   - `.scala` files -> Scala
   - `.tf` files -> Terraform
   - etc.

2. **IaC Detection**:
   - Walks directory tree for `Dockerfile`, `Jenkinsfile`
   - Checks for `k8s/`, `kustomize/`, `helm/` directories
   - Looks for Terraform files (`.tf`)

3. **Result**: `TargetProfile(mode="source", path=..., languages={...}, has_docker=True, ...)`

**For Runtime Mode** (container):

1. **Pull Image** if not present locally
2. **Inspect Image Metadata**:
   - `docker inspect` for exposed ports, environment variables
   - Detect layers and filesystem composition
3. **Result**: `TargetProfile(mode="runtime", image=..., exposed_ports=[80, 443], ...)`

**For URL Mode** (live service):

1. **Parse URL**: Extract port from URL scheme and path
2. **Set service_url**: HTTP-based plugins read this field and connect directly
3. **Optional image**: If `--image` is also provided, Docker-specific plugins (container-scanner, memory-forensics, drift-detector) still inspect the image
4. **Result**: `TargetProfile(mode="runtime", image=..., service_url="http://localhost:5000", ...)`

**Theoretical Insight**:
Profiling is a **feature extraction** step. Security scanners need context about the target to:

- Avoid wasting resources on irrelevant checks
- Tune parameters (e.g., which Semgrep rulesets to load)
- Provide relevant findings (e.g., memory forensics only run in runtime mode)

---

### 2. **ScanEngine Orchestrator** (`core/engine.py`)

**Responsibility**: Discover plugins, dispatch them to workers, aggregate results, and orchestrate the scan lifecycle.

**Why Orchestration?**

- **Parallelism**: Tools are I/O-bound (subprocess calls), so we use `ThreadPoolExecutor`
- **Standardization**: Ensures all plugins follow the same execution contract
- **Deduplication**: Handles post-processing after all plugins complete
- **Error Handling**: Collects errors from individual plugins without crashing

**How It Works**:

```python
class ScanEngine:
    def run(self, profile: TargetProfile) -> ScanReport:
        # 1. Import all plugin modules
        _import_all_plugins()

        # 2. Get registry of all concrete plugin classes
        plugins = PluginRegistry.get_all()

        # 3. Instantiate and filter by scan mode and can_handle()
        applicable_plugins = [
            p() for p in plugins
            if p.scan_modes contains profile.mode
            and p.can_handle(profile)
        ]

        # 4. Execute plugins in parallel
        findings = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(plugin.execute, profile): plugin
                for plugin in applicable_plugins
            }
            for future in as_completed(futures):
                plugin = futures[future]
                try:
                    findings.extend(future.result())
                except Exception as e:
                    report.errors.append(f"{plugin.name}: {e}")

        # 5. Deduplicate by fingerprint
        report.deduplicate()

        # 6. Sort and set timestamps
        report.sort_by_severity()
        report.finished_at = now()

        return report
```

**Plugin Discovery** (How are plugins found?):

```
_import_all_plugins():
  for module in walk(src/security_toolkit/scanners):
    __import__(module)  # This triggers plugin registration via metaclass
```

The metaclass decorator in each plugin's class definition auto-registers it:

```python
# This line is all that's needed in a plugin file:
class MyPlugin(ScannerPlugin):  # Metaclass is _PluginRegistry
    ...
    # __init_subclass__ in metaclass calls PluginRegistry.register(MyPlugin)
```

**Theoretical Insight**:
ThreadPoolExecutor is ideal here because:

- **I/O-Bound**: Each plugin blocks waiting for `subprocess.run()` to complete
- **No GIL Contention**: Threads can parallelize I/O waits efficiently
- **Simpler Than Asyncio**: No need for async/await boilerplate

---

### 3. **Plugin System** (`core/plugin.py`)

**Responsibility**: Define the plugin interface and auto-registration mechanism.

**Core Abstraction**:

```python
class ScannerPlugin(metaclass=_PluginRegistry):
    """Base class for all scanners."""

    name: str                          # Plugin identifier
    scan_modes: set[str]               # {"source"} or {"runtime"}

    def can_handle(self, profile: TargetProfile) -> bool:
        """Return True if this plugin applies to the target."""

    def execute(self, profile: TargetProfile) -> list[Finding]:
        """Run the actual scan and return findings."""
```

**Metaclass Magic** (`_PluginRegistry`):

```python
class _PluginRegistry(type):
    _plugins: ClassVar[dict[str, type[ScannerPlugin]]] = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if name != "ScannerPlugin":  # Don't register the abstract base
            mcs._plugins[name] = cls
        return cls
```

**Why Metaclasses?**

- **Automatic Registration**: On class definition, the metaclass registers the plugin
- **Zero Core Changes**: Add a new plugin file with a concrete subclass, and it's automatically discovered
- **No Plugin Registry Config File**: Plugins register themselves; no manual list to maintain

**Example Plugin**:

```python
from security_toolkit.core.plugin import ScannerPlugin
from security_toolkit.core.models import Finding, ScanMode

class SemgrepScanner(ScannerPlugin):
    name = "semgrep"
    scan_modes = {ScanMode.SOURCE}

    def can_handle(self, profile: TargetProfile) -> bool:
        # Run if Python, Go, Rust, JavaScript, etc. detected
        return bool(profile.languages & SEMGREP_LANGUAGES)

    def execute(self, profile: TargetProfile) -> list[Finding]:
        result = subprocess.run(
            ["semgrep", "scan", "--json", "--config p/security-audit", profile.path],
            capture_output=True,
            text=True,
            timeout=300
        )
        return self._parse_findings(json.loads(result.stdout))
```

**Theoretical Insight**:
This is the **Strategy Pattern** combined with **Plugin Architecture**:

- Strategy: Each plugin is an interchangeable algorithm for security scanning
- Plugin: Plugins discover and register themselves without manual configuration

---

### 4. **Core Data Models** (`core/models.py`)

**Finding** (Individual security issue):

```python
@dataclass
class Finding:
    tool: str                    # semgrep, trivy, nuclei, etc.
    rule_id: str                 # Vendor-specific rule identifier
    title: str                   # Human-readable one-liner
    description: str             # Detailed explanation
    severity: NormalizedSeverity # 1-5 scale
    file_path: str | None        # Affected file (for source findings)
    line: int                    # Line number (0 if N/A)
    category: str                # sast, sca, iac, memory, dast
    raw: dict                    # Vendor JSON (excluded from report by default)
    fingerprint: str             # SHA-256[:16] for deduplication
```

**ScanReport** (Aggregated result):

```python
@dataclass
class ScanReport:
    target: str                  # What was scanned
    mode: str                    # "source", "runtime", or "full"
    started_at: str              # ISO timestamp
    finished_at: str             # ISO timestamp
    findings: list[Finding]      # All findings
    errors: list[str]            # Tool execution errors
    metadata: dict               # Custom metadata
```

**Key Methods**:

- `deduplicate()`: Keep highest-severity per fingerprint
- `sort_by_severity()`: Descending severity order
- `severity_counts()`: Summary table
- `to_json()`: Prettified JSON for reporting
- `_verdict()`: PASS / WARN / FAIL logic

---

### 5. **Sandbox Module** (`core/sandbox.py`)

**Responsibility**: Isolate runtime scans with resource limits and network isolation.

**Why Sandboxing?**

- **Security**: Malicious containers can't escape to host
- **Resource Protection**: Prevent DoS (OOM, fork bombs, etc.)
- **Isolation**: Runtime forensics won't interfere with other containers

**How It Works**:

```python
def run_with_limits(
    func: Callable,
    *args,
    cpu_limit: int = 1,
    memory_limit_mb: int = 512,
    max_files: int = 1024,
    **kwargs
) -> Any:
    """Run func() with resource limits via resource.setrlimit()."""
    old_limits = {}
    for resource_type, limit_val in [
        (resource.RLIMIT_CPU, cpu_limit),
        (resource.RLIMIT_AS, memory_limit_mb * 1024 * 1024),
        (resource.RLIMIT_NOFILE, max_files),
    ]:
        old_limits[resource_type] = resource.getrlimit(resource_type)
        resource.setrlimit(resource_type, (limit_val, limit_val))

    try:
        return func(*args, **kwargs)
    finally:
        # Restore original limits
        for resource_type, (soft, hard) in old_limits.items():
            resource.setrlimit(resource_type, (soft, hard))
```

**Docker Sandbox Flags**:

```bash
docker run \
  --cap-drop=ALL \                    # Drop all capabilities
  --security-opt=no-new-privileges    # Can't escalate via setuid
  --memory=512m \                     # Memory limit
  --cpus=1 \                          # CPU limit
  --pids-limit=100 \                  # Process count limit
  --network=toolkit-internal \        # Isolated network
  --read-only \                       # Filesystem read-only
  image
```

**Theoretical Insight**:
Defense-in-depth: Multiple layers of isolation:

1. **OS-level**: `resource.setrlimit()`
2. **Container-level**: Docker memory/CPU/capability limits
3. **Filesystem-level**: Read-only mounts
4. **Network-level**: Isolated bridge network
5. **Process-level**: PID limit

---

### 6. **Individual Plugins**

#### **SAST Plugin** (Semgrep Scanner)

**What**: Static Application Security Testing via Semgrep.

**Why Semgrep?**

- **Semantic Pattern Matching**: Understands code structure, not just regex
- **Multi-Language**: Python, JavaScript, Java, Go, Rust, C, etc.
- **Customizable Rules**: YAML-based ruleset with built-in rules
- **Fast**: Scales to large codebases

**How**:

```python
rulesets = [
    "p/security-audit",      # OWASP Top 10 patterns
    "p/owasp-top-ten",       # OWASP classic
    "p/cwe-top-25",          # CWE Top 25
    "p/ci",                  # CI/CD pipeline issues
]
language_rulesets = {
    "python": ["p/python-security"],
    "go": ["p/golang-security"],
    "javascript": ["p/typescript", "p/javascript"],
    # etc.
}

# Run all applicable rulesets
for ruleset in applicable_rulesets:
    subprocess.run([
        "semgrep", "scan",
        "--json",
        "--config", ruleset,
        target_path
    ])
```

#### **Gitleaks Plugin** (Git Secret Scanning)

**What**: Scans Git repository history and working tree for leaked secrets.

**Why Gitleaks?**

- **Git History Scanning**: Finds secrets that were committed and later removed but still exist in Git history
- **140+ Secret Patterns**: Built-in rules for AWS, GitHub, Slack, Stripe, private keys, JWTs, etc.
- **Complementary to Semgrep**: Semgrep scans current code; Gitleaks scans the full commit history
- **Complementary to Memory Forensics**: Memory forensics finds runtime secrets; Gitleaks finds committed secrets

**How**:

```python
# Full Git history scan
subprocess.run([
    "gitleaks", "detect",
    "--source", target_path,
    "--report-format", "json",
    "--report-path", output_file,
    "--no-banner",
])

# No-git mode (working tree only, if no .git directory)
subprocess.run([
    "gitleaks", "detect",
    "--source", target_path,
    "--no-git",
    "--report-format", "json",
    "--report-path", output_file,
])
```

**Severity Mapping**: All secret leaks are HIGH or CRITICAL:

- AWS keys, private keys, GitHub PATs → CRITICAL
- Generic API keys, passwords, tokens → HIGH

#### **SCA Plugin** (Supply Chain / Software Composition Analysis)

**What**: Identifies vulnerable dependencies via Trivy.

**Why SCA?**

- **Transitive Dependencies**: Your code depends on Requests, Requests depends on urllib3, urllib3 has CVE-2023-XXXX
- **Continuous Updates**: New CVEs are discovered daily
- **Compliance**: Many regulations require dependency patching (PCI-DSS, HIPAA, SOX)

**How**:

```python
# Trivy scans package manager files: requirements.txt, go.mod, Cargo.toml, etc.
subprocess.run([
    "trivy", "filesystem",
    "--format", "json",
    "--scanners", "vuln",  # Vulnerability mode (not misconfig)
    target_path
])
```

#### **IaC Plugin** (Infrastructure-as-Code)

**What**: Detects misconfigurations in Dockerfile, Kubernetes manifests, Terraform.

**Why IaC Scanning?**

- **Configuration Drift**: Code looks good but deployment is misconfigured
- **Container Hardening**: Dockerfile practices (USER, HEALTHCHECK, version pinning)
- **Cloud Misconfiguration**: S3 buckets public, IAM policies too permissive
- **Compliance**: PCI-DSS requires specific security controls in infrastructure

**How**:

```python
# Trivy's misconfig scanner
subprocess.run([
    "trivy", "filesystem",
    "--format", "json",
    "--scanners", "misconfig",
    target_path
])
```

#### **Memory Forensics Plugin** (Runtime)

**What**: "The Break" — extracting secrets from running container memory.

**Why Memory Forensics?**

- **Secrets in Memory**: Environment variables, API keys, database passwords are loaded into memory
- **Long-Lived Containers**: Secrets in memory for days/weeks
- **Incident Response**: Detect what was accessed during a compromise

**How**:

1. **Start container** with isolated network
2. **Access /proc/1/mem** (process memory dump)
3. **Search for secrets** via regex patterns:
   - AWS keys: `AKIA[0-9A-Z]{16}`
   - Database URLs: `(mysql|postgres)://...`
   - Bearer tokens: `Bearer [A-Za-z0-9_-]+`
   - etc.
4. **Entropy analysis**: High Shannon entropy = likely random secret (not false positive)

**Theoretical Insight**:
Secrets can be extracted from memory even if:

- Never written to disk
- Overwritten in source code
- Transferred over HTTPS

This is why secrets management systems (HashiCorp Vault, AWS Secrets Manager) exist — they ensure secrets are never stored in code or container images at all.

#### **DAST Plugin** (Dynamic Application Security Testing)

**What**: Tests the application as it runs (black-box HTTP fuzzing).

**Why DAST?**

- **Runtime Behavior**: Some vulnerabilities only manifest when the app runs
- **External Perspective**: Tests what an attacker would see (no access to source)
- **Integration Issues**: Database queries, API calls, third-party integrations

**How**:

```python
# Nuclei (template-based scanner)
subprocess.run([
    "nuclei",
    "-target", url,
    "-format", "json"
])
```

#### **OWASP ZAP Plugin** (Dynamic Application Security Testing)

**What**: Comprehensive web application security testing using the OWASP Zed Attack Proxy.

**Why ZAP (in addition to Nuclei)?**

- **Active Scanning**: ZAP sends attack payloads (SQLi, XSS, CSRF) to find vulnerabilities that template-based scanners miss
- **Spider/Crawler**: Automatically discovers all endpoints, forms, and links
- **Passive Analysis**: Observes HTTP traffic for security issues (missing headers, cookies, information disclosure)
- **OWASP Standard**: Industry-standard tool recommended by OWASP; widely used in penetration testing
- **Complementary to Nuclei**: Nuclei excels at known vulnerability templates; ZAP excels at active probing and discovering unknown issues

**How**:

```python
# ZAP runs as a Docker container (official image: ghcr.io/zaproxy/zaproxy)
# Uses zap-baseline.py for automated baseline scanning
subprocess.run([
    "docker", "run", "--rm",
    "--add-host", "host.docker.internal:host-gateway",
    "-v", f"{tmpdir}:/zap/wrk:rw",
    "ghcr.io/zaproxy/zaproxy:stable",
    "zap-baseline.py",
    "-t", target_url,
    "-J", "zap_report.json",
])
```

**ZAP Risk Codes → Normalized Severity**:

- Risk 0 (Informational) → INFO
- Risk 1 (Low) → LOW
- Risk 2 (Medium) → MEDIUM
- Risk 3 (High) → HIGH

**Findings include**: CWE IDs, WASC IDs, confidence levels, affected URLs, and remediation suggestions.

---

## Data Flow and Orchestration

### Complete End-to-End Flow

```
User runs:
  docker run --rm -v /my-repo:/workspace \
    security-toolkit scan --target /workspace --output report.json

│
├─ CLI Parsing (cli.py)
│  └─ Parse args: target=/workspace, output=report.json, workers=4, fail-on=high
│
├─ Configure Logging
│  └─ Set level based on -v flag
│
├─ Profile Target (profiler.py)
│  ├─ Recursively scan /workspace for file types
│  ├─ Detect: Python, C, YAML
│  ├─ Detect: Dockerfile present
│  └─ Return: TargetProfile(mode="source", languages={python, c}, has_docker=True, ...)
│
├─ Create ScanEngine
│  └─ ScanEngine(max_workers=4)
│
├─ Run Engine (engine.py)
│  │
│  ├─ Import all plugins from security_toolkit/plugins/**/*.py
│  │  └─ Metaclass auto-registers: [SemgrepScanner, TrivySCA, ConfigScanner, ...]
│  │
│  ├─ Filter plugins by scan mode
│  │  └─ Keep: {SAST, SCA, IaC} (SOURCE mode plugins)
│  │
│  ├─ Check can_handle() for each plugin
│  │
│  │  SemgrepScanner.can_handle(profile) → True (python and c detected)
│  │  TrivySCA.can_handle(profile) → True (requirements.txt / go.mod present)
│  │  ConfigScanner.can_handle(profile) → True (Dockerfile present)
│  │  MemoryForensics.can_handle(profile) → False (not runtime mode)
│  │
│  ├─ Create ThreadPoolExecutor(max_workers=4)
│  │
│  ├─ Dispatch to workers
│  │  │
│  │  ├─ Worker 1: SemgrepScanner.execute()
│  │  │   └─ subprocess.run(["semgrep", "scan", "--json", "--config", ...])
│  │  │   └─ Parse JSON findings
│  │  │   └─ Return: [Finding(...), Finding(...), ...]
│  │  │
│  │  ├─ Worker 2: TrivySCA.execute()
│  │  │   └─ subprocess.run(["trivy", "filesystem", "--format", "json", ...])
│  │  │   └─ Parse JSON findings
│  │  │   └─ Return: [Finding(...), Finding(...), ...]
│  │  │
│  │  └─ Worker 3: ConfigScanner.execute()
│  │      └─ subprocess.run(["trivy", "filesystem", "--scanners", "misconfig", ...])
│  │      └─ Parse JSON findings
│  │      └─ Return: [Finding(...), Finding(...), ...]
│  │
│  ├─ Wait for all workers (as_completed)
│  │  └─ Aggregate: findings = [all results from all workers]
│  │
│  ├─ Deduplicate (report.deduplicate())
│  │  └─ Group by fingerprint, keep highest severity per group
│  │
│  ├─ Sort (report.sort_by_severity())
│  │  └─ Findings ordered CRITICAL, HIGH, MEDIUM, LOW, INFO
│  │
│  ├─ Set timestamps
│  │  └─ report.finished_at = now()
│  │
│  └─ Return: ScanReport with deduplicated, sorted findings
│
├─ Print Console Report (console_report.py)
│  ├─ Rich table with severity, tool, rule, title, location
│  ├─ Severity summary (counts by level)
│  └─ Verdict badge (PASS / WARN / FAIL)
│
├─ Write JSON Report (reporting/json_report.py)
│  ├─ call report.to_json(include_raw=False)
│  ├─ Group findings by category (sast, sca, iac, etc.)
│  ├─ Structure: { report, summary, findings_by_category, errors }
│  └─ Write to /workspace/report.json with 2-space indentation
│
├─ Determine Exit Code
│  ├─ fail_threshold = HIGH (from --fail-on high)
│  ├─ if any finding.severity >= HIGH:
│  │    exit(1)  ← Pipeline fails
│  └─ else:
│      exit(0)  ← Pipeline passes
│
└─ Done
```

---

## Plugin Architecture: Metaclass Pattern

### Why Metaclasses for Plugin Registration?

**Traditional Approach** (Bad):

```python
# In core/engine.py
PLUGINS = [
    "security_toolkit.plugins.sast.semgrep_scanner.SemgrepScanner",
    "security_toolkit.plugins.sca.trivy_sca.TrivySCA",
    "security_toolkit.plugins.iac.config_scanner.ConfigScanner",
    # ... manually add every plugin
]

# Problem: Developer adds new plugin → MUST update this list
# → Many places to forget/cause bugs → maintenance burden
```

**Metaclass Approach** (Good):

```python
# In core/plugin.py
class _PluginRegistry(type):
    _plugins: ClassVar[dict[str, type[ScannerPlugin]]] = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if bases and ScannerPlugin in bases.__mro__:
            mcs._plugins[name] = cls  # Auto-register
        return cls

class ScannerPlugin(metaclass=_PluginRegistry):
    ...

# In each plugin file:
class SemgrepScanner(ScannerPlugin):  # Metaclass is inherited
    ...
    # Auto-registered on class definition; no manual list needed

# Problem: Solved! Add plugin → Auto-discovered
```

### How It Works Internally

```python
# When this line executes:
class SemgrepScanner(ScannerPlugin):
    name = "semgrep"
    ...

# Python calls: _PluginRegistry.__new__()
# Which calls: mcs._plugins["SemgrepScanner"] = SemgrepScanner
# Result: Plugin is registered without any other code running
```

**Getting Registered Plugins**:

```python
def get_registered_plugins() -> dict[str, type[ScannerPlugin]]:
    return _PluginRegistry._plugins.copy()

def instantiate_plugins() -> list[ScannerPlugin]:
    return [plugin_class() for plugin_class in get_registered_plugins().values()]
```

### Why This Matters

| Aspect                      | Traditional                 | Metaclass               |
| --------------------------- | --------------------------- | ----------------------- |
| Adding new plugin           | Edit core; edit plugin file | Edit plugin file only   |
| Discovering plugins         | Hardcoded list              | Automatic via metaclass |
| Risk of forgetting a plugin | High                        | Zero                    |
| Testability                 | Tight coupling              | Loose coupling          |
| Extensibility               | Requires core changes       | No core changes         |

---

## Key Design Choices

### 1. **Thread-Based Parallelism (Not Async)**

**Choice**: Use `ThreadPoolExecutor` for parallel plugin execution.

**Alternatives Considered**:

- `multiprocessing`: Higher overhead, overkill for I/O
- `asyncio`: Requires rewriting plugin interface as async
- Sequential (no parallelism): Slow

**Why ThreadPoolExecutor?**:

- **I/O-Bound Nature**: Plugins block on `subprocess.run()`
- **GIL Relief**: Even with GIL, I/O releases it, allowing parallelism
- **Simplicity**: No async/await boilerplate
- **Production-Ready**: Well-tested, battle-hardened

**Math**:

```
Sequential: scan_sast=120s, scan_sca=60s, scan_iac=30s
           Total: 120+60+30 = 210s

Parallel (3 workers): max(120, 60, 30) = 120s
                      Speedup: 210/120 = 1.75x faster
```

---

### 2. **Deduplication via Fingerprint (Not Tool Dedup)**

**Choice**: Hash on `(rule_id, file_path, line, title)` for deduplication.

**Alternatives**:

- **No dedup**: Duplicate findings everywhere (noise)
- **Tool dedup**: Keep only highest-severity tool per rule (loses info)
- **Fingerprint dedup** (chosen): Keep unique (rule, file, line) combos; highest severity wins

**Why Fingerprinting?**:

- **Handles Overlapping Rulesets**: Semgrep's "security-audit" and "owasp-top-ten" both detect XSS → same fingerprint → deduplicated
- **Stable**: Same finding always produces same fingerprint
- **Tool-Agnostic**: Works across Semgrep, Trivy, Nuclei

**Example**:

```
Finding 1 (Semgrep): rule=AWS-HARDCODED, file=app.py, line=42
Finding 2 (Trivy): rule=CVE-2024-XXXX, file=app.py, line=42

Different rules, same location → Different fingerprints → Both kept

Finding 3 (Semgrep ruleset A): rule=PATTERN-123, file=app.py, line=50
Finding 4 (Semgrep ruleset B): rule=PATTERN-456, file=app.py, line=50
                                (different rule but same line/title)

Same pattern, different rule ID → Same fingerprint → Deduplicated
```

---

### 3. **Severity Normalization (Not Tool-Native)**

**Choice**: Map all vendor labels to unified 1-5 `NormalizedSeverity` enum.

**Alternatives**:

- Keep tool-native labels (HIGH, CRITICAL, ERROR, WARNING, ...) → Unmappable
- String comparison ("high" < "critical"? Undefined)
- Custom scoring (CVSSv3 score) → Requires vendor data

**Why Normalization?**:

- **Cross-Tool Comparison**: Can compare findings from different scanners
- **Consistent CI/CD Gate**: `--fail-on HIGH` works regardless of tool
- **Sortable**: IntEnum (1-5) is naturally orderable

**Mapping**:
| Tool | Native Label | Normalized |
|------|--------------|-----------|
| Trivy | CRITICAL | 5 |
| Trivy | HIGH | 4 |
| Semgrep | ERROR | 4 |
| Semgrep | WARNING | 3 |
| Nuclei | HIGH | 4 |
| Nuclei | INFO | 1 |

---

### 4. **Self-Contained Folder Deployment**

**Choice**: Everything (Dockerfile, docker-compose, pyproject.toml, source code) lives in `security_toolkit/`.

**Alternatives**:

- Separate: Dockerfile at `/`, pyproject at `/`, source in `/security_toolkit/`
- Monorepo: Toolkit is one of many tools in a larger repo

**Why Self-Contained?**:

- **Easy Distribution**: `git clone ... && cd security_toolkit && docker build .`
- **Few Moving Parts**: Everything needed is in one place
- **Encapsulation**: Toolkit is independent; doesn't pollute repo root
- **Clear Ownership**: All toolkit files are in one directory tree

**Implication**: Build context is the `security_toolkit/` directory itself:

```dockerfile
# Build from: docker build -f Dockerfile -t security-toolkit .
# (when CWD is security_toolkit/)

COPY pyproject.toml ./pyproject.toml
COPY core/ ./security_toolkit/core/
# (not COPY ../security_toolkit/core/ because context IS security_toolkit/)
```

---

### 5. **No-Build Philosophy**

**Choice**: Analyze artifacts without compiling source code.

**Alternatives**:

- Compile first (not done):
  - Requires language-specific toolchains
  - Introduces supply-chain risk
  - Slow
  - Language-specific

**Why No-Build?**:

- **Supply Chain Security**: Don't download potentially compromised build tools
- **Universality**: Works on any language equally
- **Speed**: No compile step
- **Simplicity**: Just read the files

**Implication**: Relies on static analysis (Semgrep) and package metadata (Trivy) instead of compiled artifacts.

---

### 6. **Docker-First Deployment**

**Choice**: All external tools are bundled in the Docker image. Plugins require their tools and skip cleanly if unavailable.

**Example**:

```python
class IaCConfigScanner(ScannerPlugin):
    def can_handle(self, profile: TargetProfile) -> bool:
        if not check_tool_available("trivy"):
            return False
        return profile.has_docker or profile.has_k8s or profile.has_terraform
```

If `trivy` binary is not found:

- `can_handle()` returns False
- Engine skips this plugin
- Scan continues with other plugins

**Why?**:

- **Simplicity**: No built-in fallback implementations to maintain
- **Consistency**: Same tool produces findings everywhere
- **Docker Image**: All tools are guaranteed present in the bundled image

---

### 7. **Human-Readable JSON Output**

**Choice**: Prettified JSON with findings grouped by category, timestamps, verdict, severity summary.

**Alternatives**:

- Minified JSON (hard to read in terminal)
- CSV (less structured, doesn't capture hierarchies)
- HTML report (requires browser)

**Why This Format?**:

- **Readable in Terminal**: Pretty-printed with 2-space indentation
- **Machine-Parseable**: Valid JSON for CI/CD integrations
- **Structured**: Grouped by category (sast, sca, iac, etc.)
- **Tool-Agnostic**: No vendor-specific fields

**Report Structure**:

```json
{
  "report": { target, mode, started_at, finished_at, verdict },
  "summary": { total_findings, by_severity },
  "plugins": { total_registered, executed, failed, skipped },
  "findings_by_category": { sast, sca, iac, ... },
  "errors": [list of tool errors]
}
```

---

### 8. **Predictable Report Filenames (No Timestamps)**

**Choice**: Generate `report.json` and `report.md` without timestamps, or with user-specified stem.

**Alternatives**:

- Timestamped filenames (`security_report_20260212_051648.json`) — makes each run unique but unpredictable
- Single hardcoded name with overwrite — loses history
- Custom naming with user-provided template — more complex CLI

**Why Predictable Names?**:

- **CI/CD Integration**: Pipelines can expect stable paths (`/reports/report.json`)
- **Reproducibility**: Running the same scan produces the same filename
- **Simplicity**: No need to parse timestamps or glob patterns
- **Consistency**: JSON and Markdown reports share the same stem

**Output Examples**:

```bash
# Directory mode: creates /reports/report.json + /reports/report.md
security_toolkit scan --target ./my-app --output /reports

# File stem mode: creates ./my-scan.json + ./my-scan.md
security_toolkit scan --target ./my-app --output ./my-scan

# File path mode: creates /custom/path/report.json + /custom/path/report.md
security_toolkit full --target ./my-app --image my-app:latest --output /custom/path/report.json
```

---

## Security Scanning Fundamentals

### **The Three Pillars of Application Security**

#### **1. SAST (Static Application Security Testing)**

- **What**: Analyze source code without running it
- **When**: Pre-commit, PR review, pre-deployment
- **Trade-off**: Fast but many false positives
- **Tool**: Semgrep (semantic pattern matching)

#### **2. SCA (Software Composition Analysis)**

- **What**: Identify vulnerable dependencies
- **When**: Every build, continuous
- **Trade-off**: Effective but dependency-heavy codebases get noisy
- **Tool**: Trivy (CVE database lookup)

#### **3. DAST (Dynamic Application Security Testing)**

- **What**: Test the running application (black-box)
- **When**: Post-deployment, staging environment
- **Trade-off**: Catches runtime issues missed by static analysis
- **Tool**: Nuclei (HTTP fuzzing)

### **Categories of Vulnerabilities**

| Category              | Examples                            | Detected By         |
| --------------------- | ----------------------------------- | ------------------- |
| **Code Flaws**        | Injection, XSS, Path traversal      | SAST (Semgrep)      |
| **Dependencies**      | Outdated libraries, known CVEs      | SCA (Trivy)         |
| **Configuration**     | Hardcoded secrets, weak permissions | SAST, IaC scanning  |
| **Infrastructure**    | Exposed ports, missing HEALTHCHECK  | IaC scanning        |
| **Committed Secrets** | API keys, passwords in Git history  | Gitleaks            |
| **Runtime Behavior**  | XXE, SSRF, authentication bypass    | DAST (Nuclei + ZAP) |
| **Secrets**           | API keys, passwords in memory       | Memory forensics    |
| **Drift**             | Unauthorized file changes, rootkits | Drift detector      |

### **Why Multi-Tool Approach?**

Each tool excels in a specific domain:

- **Semgrep**: Semantic code analysis (catches complex patterns)
- **Gitleaks**: Git history secret detection (catches committed credentials)
- **Trivy**: CVE database (comprehensive dependency scanning)
- **Nuclei**: HTTP fuzzing templates (community-driven web vulnerability patterns)
- **OWASP ZAP**: Active/passive web scanning (spider, active injection testing, traffic analysis)

No single tool can cover all these domains equally well.

---

## Theoretical Procedures

### **Procedure 1: How Semgrep Rules Work**

**Step 1: Parse Code to AST**

```
Source Code:
    user_input = request.args.get('data')
    os.system(f"echo {user_input}")

Abstract Syntax Tree (AST):
    FunctionCall(
        name="os.system",
        args=[
            f-string(
                template="echo {...}",
                interpolations=[Variable(name="user_input", ...)]
            )
        ]
    )
```

**Step 2: Pattern Matching**

```yaml
# Semgrep rule (YAML)
rules:
  - id: python.lang.security.os-system-dynamic
    patterns:
      - pattern: |
          $VALUE = request.args.get(...)
          os.system(f"...{$VALUE}...")
      - pattern-not-inside: |
          # Exclude if input is validated
          if $VALUE in WHITELIST:
            ...
    message: 'Potential command injection: user input to os.system()'
    severity: HIGH
```

**Step 3: Report Finding**

```
Match found at:
  File: /app.py
  Line: 42
  Patterns matched: os.system() with interpolated user input
  Severity: HIGH
```

### **Procedure 2: How Trivy Detects CVEs**

**Step 1: Extract Dependency Metadata**

```
requirements.txt:
    requests==2.28.0
    flask==2.3.0
    urllib3==1.26.5

Parse → [
    Package(name="requests", version="2.28.0"),
    Package(name="flask", version="2.3.0"),
    Package(name="urllib3", version="1.26.5"),
]
```

**Step 2: Cross-Reference CVE Database**

```
Trivy Database (updated hourly):
    urllib3==1.26.5:
      - CVE-2023-45234
      - CVE-2023-45235

    flask==2.3.0:
      - (no CVEs known)
```

**Step 3: Report Vulnerability**

```
CVE-2023-45234:
  Package: urllib3
  Fixed in: 1.26.6, 2.0.0 (or later)
  User has: 1.26.5
  Status: VULNERABLE
  Severity: MEDIUM
```

### **Procedure 3: How Memory Forensics Extracts Secrets**

**Step 1: Container Starts**

```bash
docker run -d my-app:latest

Environment Variables (loaded into memory):
  DB_PASSWORD=super-secret-123
  AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
  API_TOKEN=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Step 2: Memory Dump**

```bash
docker exec <container> cat /proc/1/mem | xxd | head -20

Output (hex):
  00000000: 7375 7065 722d 7365 6372 6574 2d31 3233  super-secret-123
  00000010: 4157 5353 5f53 4543 5245 5420 7755 6a61  AWS_SECRET_ACCESS_KEY wuja
  ...
```

**Step 3: Pattern Matching**

```python
PATTERNS = {
    "AWS Key": r"AKIA[0-9A-Z]{16}",
    "Database URL": r"(mysql|postgres)://([^:]+):([^@]+)@",
    "Bearer Token": r"Bearer [A-Za-z0-9_-]+",
}

# Regex scan through memory dump
if re.search(r"AKIA[0-9A-Z]{16}", memory_content):
    Finding(
        title="AWS Secret Key Found in Memory",
        description="Container memory contains AWS access key",
        severity=CRITICAL
    )
```

**Step 4: Entropy Filtering** (False Positive Reduction)

```python
def entropy(data: str) -> float:
    # Shannon entropy: 0.0 (uniform) to 8.0 (maximum randomness)
    freq = {}
    for char in data:
        freq[char] = freq.get(char, 0) + 1

    entropy = sum(
        -(count / len(data)) * log2(count / len(data))
        for count in freq.values()
    ) / 8.0
    return entropy

# AWS secret key has high entropy (nearly random)
# Entropy ≈ 0.95 → Likely real secret, not false positive

# But "ababababab" has low entropy
# Entropy ≈ 0.10 → Likely false positive
```

### **Procedure 4: IaC Linting**

**Step 1: Parse Dockerfile**

```dockerfile
FROM node:latest
WORKDIR /app
COPY . /app
RUN npm install
EXPOSE 3000
CMD ["npm", "start"]
```

**Step 2: Check Best Practices**

```
Issue 1: FROM node:latest
  → Problem: Using :latest means rebuilds will pull different images
  → Fix: Pin version: FROM node:18.19.0

Issue 2: No USER directive
  → Problem: Container runs as root
  → Fix: Add USER appuser before CMD

Issue 3: No HEALTHCHECK
  → Problem: Orchestrator can't detect hung processes
  → Fix: Add HEALTHCHECK --interval=30s CMD curl http://localhost:3000/health
```

**Step 3: Report Issues**

```
Category: IaC
Tool: trivy
Rule: DS-0005 (Base image has vulnerability)
Severity: MEDIUM
Location: Dockerfile:1
```

### **Procedure 5: Deduplication Algorithm**

**Input**: List of findings from multiple plugins

```
Finding 1: Semgrep "XSS" at app.py:42 (MEDIUM)
Finding 2: Semgrep "XSS" at app.py:42 (HIGH)  ← Overlapping ruleset
Finding 3: Trivy CVE-2024-123 at requirements.txt (CRITICAL)
```

**Step 1: Compute Fingerprints**

```python
fp1 = SHA256("xss-rule-001|app.py|42|XSS vulnerability")[:16]
     = "a1b2c3d4e5f6g7h8"

fp2 = SHA256("xss-rule-002|app.py|42|XSS vulnerability")[:16]
     = "a1b2c3d4e5f6g7h8"  ← Same fingerprint!

fp3 = SHA256("cve-2024-123|requirements.txt|0|CVE-2024-123")[:16]
     = "x9y8z7w6v5u4t3s2"  ← Different fingerprint
```

**Step 2: Group by Fingerprint**

```
Group 1 (fp = "a1b2c3d4e5f6g7h8"):
  - Finding 1 (MEDIUM)
  - Finding 2 (HIGH)

Group 2 (fp = "x9y8z7w6v5u4t3s2"):
  - Finding 3 (CRITICAL)
```

**Step 3: Keep Highest Severity Per Group**

```
Group 1 → Keep Finding 2 (HIGH > MEDIUM)
Group 2 → Keep Finding 3 (CRITICAL)

Final result: [Finding 2, Finding 3]
```

---

## False-Positive Reduction

### The Problem

Security scanning tools cast a wide net. Rules like Semgrep's `dynamic-urllib-use-detected`
flag any dynamic URL construction as a potential SSRF vector. In a security toolkit that
uses `urllib` internally for health checks, this produces 20+ MEDIUM findings that are
definitively not vulnerabilities.

### The Solution

The Semgrep plugin implements a **post-processing false-positive reduction** pipeline:

1. **Noisy Rule Detection**: Rules in `_NOISY_RULES` (e.g., `dynamic-urllib-use-detected`)
   are tracked separately.

2. **Threshold Check**: If a noisy rule fires >= `_FP_CONSOLIDATION_THRESHOLD` (3) times,
   consolidation is triggered.

3. **Safe Path Classification**: Each hit is checked against `_SAFE_URLLIB_PATH_PATTERNS`
   (e.g., `plugins/`, `tests/`, `utils/`). Hits in internal/tool code are classified as safe;
   hits in user-facing code (routes, views, handlers) are kept.

4. **Consolidation**: Safe hits are collapsed into a single **INFO-level advisory** that
   lists all locations but doesn't inflate the severity summary.

5. **Unsafe hits preserved**: Any hit in non-tool code retains its original severity.

```
Before FP reduction:  32 findings (2 CRITICAL, 7 HIGH, 21 MEDIUM, 2 LOW)
After FP reduction:   15 findings (2 CRITICAL, 7 HIGH, 3 MEDIUM, 2 LOW, 1 INFO)

20 noisy MEDIUM findings → 1 consolidated INFO advisory (-53% noise)
```

---

## Direct URL Scanning (`--url` Mode)

### The Problem

When the security toolkit runs inside a Docker container, it starts target containers
via the host's Docker daemon (docker.sock). Published ports map to the **host's localhost**,
but the toolkit container can't reach `host:localhost` — it has its own network namespace.
This causes HTTP-based plugins (DAST, ZAP, load-tester, custom-detectors, resource-monitor)
to fail health checks and return 0 findings.

### The Solution

The `--url` option allows pointing HTTP-based runtime plugins at a live service directly:

```bash
# Start your app
python app.py  # listening on localhost:5000

# Scan it with --url
security_toolkit inspect --url http://localhost:5000
security_toolkit full --target ./my-app --image my-app:latest --url http://localhost:5000
```

### How It Works

1. **TargetProfile** gains a `service_url` field.
2. **Profiler** accepts `url` parameter, allows combining with `image`.
3. **HTTP plugins** check `profile.service_url` first:
   - If set: skip container startup, connect directly to the URL.
   - If not set: fall back to existing behavior (start container, discover port).
4. **Docker-specific plugins** (container-scanner, memory-forensics, drift-detector)
   still use `--image` and are unaffected.

### Plugin Coverage Matrix

| Plugin            |     `--image` only      |  `--url` only   |  `--image` + `--url`  |
| ----------------- | :---------------------: | :-------------: | :-------------------: |
| DAST (Nuclei)     |     Container start     |   Direct URL    |      Direct URL       |
| ZAP               |     Container start     |   Direct URL    |      Direct URL       |
| Load Tester       |     Container start     |   Direct URL    |      Direct URL       |
| Custom Detectors  |     Container start     |   Direct URL    |      Direct URL       |
| Resource Monitor  | Container start + stats | URL checks only | Container stats + URL |
| Memory Forensics  |    Container inspect    |     Skipped     |   Container inspect   |
| Drift Detector    |     Container diff      |     Skipped     |    Container diff     |
| Container Scanner |       Image scan        |     Skipped     |      Image scan       |

---

## Plugin Rulesets and Detection Rules

This section documents all rulesets, patterns, rules, and detection logic used by each of the 12 plugins.

### 1. Semgrep Scanner (SAST - python.lang.security.\*)

**Tool:** Semgrep

**Mandatory Rulesets (Applied to All Languages):**

- `p/security-audit` — General vulnerability patterns
- `p/secrets` — Hardcoded credentials detection
- `p/owasp-top-ten` — OWASP Top 10 patterns
- `p/ci` — CI/CD pipeline security flaws
- `p/supply-chain` — Supply chain attack vectors

**Language-Specific Rulesets (Dynamic):**

- `p/python` — Python security rules (if .py files detected)
- `p/javascript` — JavaScript rules (if .js files)
- `p/typescript` — TypeScript rules (if .ts files)
- `p/golang` — Go rules (if .go files)
- `p/rust` — Rust rules (if .rs files)
- `p/java` — Java rules (if .java files)
- `p/ruby` — Ruby rules (if .rb files)
- `p/php` — PHP rules (if .php files)
- `p/c` — C rules (if .c/.h files)
- `p/csharp` — C# rules (if .cs files)
- `p/kotlin` — Kotlin rules (if .kt files)
- `p/scala` — Scala rules (if .scala files)
- `p/swift` — Swift rules (if .swift files)
- `p/bash` — Bash rules (if .sh files)
- `p/elixir` — Elixir rules (if .ex/.exs files)

**Configuration:**

- Timeout: 600 seconds
- No Git ignore honored (scans all files)
- Output format: JSON

**False-Positive Reduction:**

- Noisy rule: `dynamic-urllib-use-detected`
- Consolidation threshold: ≥3 occurrences in safe paths
- Safe path patterns: `plugins/`, `tests?/`, `utils?/`, `tools?/`, `scripts?/`, `internal/`, `health*`
- Result: 20+ false positives → 1 INFO advisory (-53% noise)

---

### 2. Gitleaks Scanner (Secrets)

**Tool:** Gitleaks

**Secret Detection Rules (19 types):**

| Rule ID                   | Secret Type                  | Severity |
| ------------------------- | ---------------------------- | -------- |
| `aws-access-token`        | AWS Access Token             | CRITICAL |
| `aws-secret-access-key`   | AWS Secret Key               | CRITICAL |
| `private-key`             | Generic Private Key          | CRITICAL |
| `rsa-private-key`         | RSA Private Key              | CRITICAL |
| `github-pat`              | GitHub Personal Access Token | CRITICAL |
| `github-fine-grained-pat` | GitHub Fine-Grained PAT      | CRITICAL |
| `github-oauth`            | GitHub OAuth Token           | CRITICAL |
| `gitlab-pat`              | GitLab Personal Access Token | CRITICAL |
| `stripe-api-key`          | Stripe API Key               | CRITICAL |
| `generic-api-key`         | Generic API Key              | HIGH     |
| `generic-password`        | Generic Password             | HIGH     |
| `slack-token`             | Slack Bot Token              | HIGH     |
| `slack-webhook`           | Slack Webhook                | HIGH     |
| `twilio-api-key`          | Twilio API Key               | HIGH     |
| `sendgrid-api-key`        | SendGrid API Key             | HIGH     |
| `npm-access-token`        | NPM Registry Token           | HIGH     |
| `pypi-upload-token`       | PyPI Upload Token            | HIGH     |
| `hashicorp-tf-api-token`  | Terraform API Token          | HIGH     |
| `jwt`                     | JSON Web Token               | HIGH     |

**Configuration:**

- Timeout: 300 seconds
- Modes: Git history scan (if .git exists) OR working tree only (if no .git)
- Output format: JSON

---

### 3. Trivy SCA Scanner (Software Composition Analysis)

**Tool:** Trivy (filesystem mode, vuln scanner)

**Detection:**

- Scans: `requirements.txt`, `go.mod`, `Cargo.toml`, `package.json`, `pom.xml`, etc.
- Matches: Package name + version against CVE database
- Output: CVE-XXXX-XXXXX with severity from NVD

**Rule Format:**

- Rule ID: CVE ID (e.g., CVE-2024-1234)
- Title: `{PackageName} {Version}: {CVE-ID}`
- Severity: CRITICAL, HIGH, MEDIUM, LOW (from CVE database)

**Configuration:**

- Timeout: 600 seconds
- Quiet mode: Enabled
- Scanner type: `vuln`

---

### 4. IaC Config Scanner (Infrastructure-as-Code)

**Tool:** Trivy (filesystem mode, misconfig scanner)

**Detects Misconfigurations In:**

- Dockerfiles (e.g., `DS-0002` running as root, `DS-0026` missing HEALTHCHECK)
- Kubernetes YAML (e.g., `AVD-KSV-001` privileged containers)
- Terraform (e.g., `AVD-AWS-0001` public S3 bucket)

**Example Rules:**

- `DS-0031` — Secrets passed via build args or env vars (CRITICAL)
- `DS-0002` — Container running as root user (HIGH)
- `DS-0026` — Missing HEALTHCHECK (LOW)

**Configuration:**

- Timeout: 300 seconds
- Quiet mode: Enabled
- Scanner type: `misconfig`
- Activated only if has_docker, has_k8s, or has_terraform

---

### 5. DAST HTTP Fuzzer (Nuclei)

**Tool:** Nuclei (ProjectDiscovery)

**Detection Method:**

- Uses Nuclei community templates
- Discovered endpoints tested against running service
- Performs dynamic/black-box testing

**Severity Levels:**

- `critical` → CRITICAL
- `high` → HIGH
- `medium` → MEDIUM
- `low` → LOW
- `info` → INFO

**Configuration:**

- Web Ports Detected: 80, 443, 8080, 8443, 3000, 5000, 8000, 9000
- Container Limits: 0.5 CPU, 256 MB memory
- Health check: 10 retries, 2-second delay
- Timeout: 300 seconds

---

### 6. OWASP ZAP Scanner (DAST)

**Tool:** OWASP ZAP (ghcr.io/zaproxy/zaproxy:stable)

**Scanning Methods:**

1. Spider/Crawler — Endpoint discovery
2. Passive Scan — HTTP traffic analysis
3. Active Scan — Attack payload testing (SQLi, XSS, CSRF)
4. AJAX Spider — JavaScript apps

**Risk to Severity Mapping:**
| ZAP Risk | Normalized |
|----------|-----------|
| 0 (Informational) | INFO |
| 1 (Low) | LOW |
| 2 (Medium) | MEDIUM |
| 3 (High) | HIGH |

**Confidence Levels:**
| Code | Label |
|------|-------|
| 0 | false-positive |
| 1 | low |
| 2 | medium |
| 3 | high |
| 4 | confirmed |

**Example Rule IDs:**

- `ZAP-10038` — Missing Content Security Policy header
- `ZAP-90004` — Insufficient isolation against Spectre
- `ZAP-10063` — Missing Permissions-Policy header
- `ZAP-10036` — Server version leaked in HTTP headers
- `ZAP-10021` — Missing X-Content-Type-Options header

**Configuration:**

- Container Limits: 0.5 CPU, 256 MB memory
- Scan Baseline: `zap-baseline.py -I -d`
- Timeout: 300 seconds

---

### 7. Container Image Scanner (Runtime)

**Tool:** Trivy (image mode)

**Detects:**

- OS-level package vulnerabilities (from OS package managers)
- Application dependencies vulnerabilities
- Secrets in container filesystem

**Rule ID Format:** CVE-XXXX-XXXXX

**Configuration:**

- Timeout: 600 seconds
- Quiet mode: Enabled
- Scans entire image filesystem

---

### 8. Memory Forensics Scanner (Runtime Secrets)

**Tool:** Custom pattern matching + Docker memory access

**Secret Detection Patterns (20 patterns):**

| Rule ID          | Pattern                | Regex                                                                                             | Severity |
| ---------------- | ---------------------- | ------------------------------------------------------------------------------------------------- | -------- |
| `MEM-SECRET-001` | AWS Access Key ID      | `AKIA[0-9A-Z]{16}`                                                                                | CRITICAL |
| `MEM-SECRET-002` | AWS Secret Key         | `(?:aws_secret_access_key\|secret)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})`                     | CRITICAL |
| `MEM-SECRET-003` | Generic API Key        | `(?:api[_-]?key\|apikey)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})`                              | CRITICAL |
| `MEM-SECRET-004` | Generic Password       | `(?:password\|passwd\|pwd)['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})`                                   | CRITICAL |
| `MEM-SECRET-005` | DB Connection String   | `(?:mysql\|postgres\|mongodb\|redis)://[^\s]{10,}`                                                | CRITICAL |
| `MEM-SECRET-006` | Private Key Block      | `-----BEGIN (?:RSA\|EC\|DSA )? PRIVATE KEY-----`                                                  | CRITICAL |
| `MEM-SECRET-007` | Bearer Token           | `Bearer\s+[A-Za-z0-9\-._~+/]+=*`                                                                  | CRITICAL |
| `MEM-SECRET-008` | GitHub Token           | `gh[pousr]_[A-Za-z0-9_]{36,}`                                                                     | CRITICAL |
| `MEM-SECRET-009` | Slack Token            | `xox[baprs]-[0-9A-Za-z\-]{10,}`                                                                   | CRITICAL |
| `MEM-SECRET-010` | JWT Token              | `eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}`                                   | CRITICAL |
| `MEM-SECRET-011` | Google Cloud API Key   | `AIza[0-9A-Za-z\-_]{35}`                                                                          | CRITICAL |
| `MEM-SECRET-012` | Stripe Secret Key      | `sk_live_[0-9a-zA-Z]{24,}`                                                                        | CRITICAL |
| `MEM-SECRET-013` | Stripe Publishable Key | `pk_live_[0-9a-zA-Z]{24,}`                                                                        | CRITICAL |
| `MEM-SECRET-014` | SendGrid API Key       | `SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}`                                                      | CRITICAL |
| `MEM-SECRET-015` | Mailchimp API Key      | `[0-9a-f]{32}-us[0-9]{1,2}`                                                                       | CRITICAL |
| `MEM-SECRET-016` | Twilio API Key         | `SK[0-9a-fA-F]{32}`                                                                               | CRITICAL |
| `MEM-SECRET-017` | HashiCorp Vault Token  | `hvs\.[A-Za-z0-9_\-]{24,}`                                                                        | CRITICAL |
| `MEM-SECRET-018` | Heroku API Key         | `(?:HEROKU\|heroku).*[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}` | CRITICAL |
| `MEM-SECRET-019` | PEM Certificate        | `-----BEGIN CERTIFICATE-----`                                                                     | CRITICAL |
| `MEM-SECRET-020` | Hex-Encoded Secret     | `(?:secret\|token\|key)['\"]?\s*[:=]\s*['\"]?[0-9a-f]{64}`                                        | CRITICAL |

**High-Entropy Detection:**

- Rule ID: `MEM-ENTROPY-001`
- Pattern: High Shannon entropy (>5.0) in 20-200 char strings
- Regex: `^[A-Za-z0-9+/=_\-.:]{20,}$` (includes colons and dots for token patterns)
- False-positive exclusions: PATH=, HOME=, LANG=, TERM=, HOSTNAME=, SHLVL=
- Severity: HIGH

**Extraction Methods (3-tier, all always run):**

1. **Tier 1**: `/proc/1/mem` via chunked reads of mapped memory regions (requires SYS_PTRACE)
   - Reads only mapped readable regions, skips regions >10MB
   - Extracts strings line-by-line to avoid OOM
2. **Tier 2**: `env` command via docker exec for current process environment
3. **Tier 3**: `docker inspect` for container's configured environment variables

Lines from all tiers are deduplicated before pattern scanning.

**Configuration:**

- Container memory limit: **512 MB** (increased from 256 MB to handle Python fallback)
- Container initialization: Polls `docker inspect --format '{{.State.Running}}'` until healthy (up to 15 seconds)
- Memory dump timeout: 30 seconds
- Redaction: First 6 + "..." + last 4 chars

---

### 9. Drift Detector (Runtime)

**Tool:** Docker `docker diff` command

**Detection:**

- Rule ID: `DRIFT-001`
- Detects: Added (A), Modified (M), Deleted (D) files
- Filters out directory-only changes
- Reports: First 10 files + total count

**Configuration:**

- Container initialization: 5-second delay
- Diff timeout: 30 seconds

---

### 10. Load Tester (Race Condition Detection)

**Tool:** Custom concurrent HTTP client

**Test 1: Counter Race Condition**

- Rule ID: `RACE-001`
- Endpoint: `/increment`
- Configuration: 10 concurrent workers, 50 requests/endpoint
- Detection: Duplicate counter values = lost updates
- Severity: HIGH

**Test 2: Resource Exhaustion / Missing Rate Limit**

- Rule ID: `RACE-002`
- Endpoint: `/allocate?size=100000`
- Configuration: 20 concurrent requests
- Threshold: ≥15 successful = missing rate limit
- Severity: MEDIUM

**Configuration:**

- Container Limits: 0.5 CPU, 256 MB
- Health check: 10 retries, 2-second delay
- Timeout: 300 seconds

---

### 11. Resource Monitor (Memory & Connection Leaks)

**Tool:** Docker stats + custom endpoint probing

**Test 1: Memory Leak Detection**

- Rule ID: `RESLEAK-001`
- Endpoint: `/leak`, `/allocate?size=500000`
- Configuration: Baseline vs final measurement (3-sec window)
- Threshold: Growth > 50%
- Severity: MEDIUM

**Test 2: Connection Leak Detection**

- Rule ID: `RESLEAK-002`
- Endpoint: `/connection-leak`
- Configuration: 10 requests
- Threshold: > 5 unclosed connections
- Severity: MEDIUM

**Test 3: Unbounded Allocation (URL-only)**

- Rule ID: `RESLEAK-003`
- Endpoint: `/allocate?size=500000`
- Configuration: 5 sequential requests
- Threshold: ≥5 successful = no limit
- Severity: MEDIUM

**Configuration:**

- Memory Limits: 512 MB
- CPU Limits: 0.5
- Memory Growth Threshold: 50%
- Timeout: 300 seconds

---

### 12. Custom Runtime Detectors

**Tool:** Custom HTTP probing

**Test 1: Debug Mode Detection**

- Rule ID: `CUSTOM-DEBUG-001` (CRITICAL)
- Endpoint: `/console`, `/?__debugger__=yes`
- Indicators: "debugger", "werkzeug", "interactive", "traceback", "console"

- Rule ID: `CUSTOM-DEBUG-002` (HIGH)
- Detection: Server header contains "werkzeug" or "development"

**Test 2: Secret Endpoint Exposure**

- Rule ID: `CUSTOM-SECRETS-001` (CRITICAL)
- Monitored Endpoints: `/info`, `/env`, `/config`, `/debug`, `/process-info`, `/admin`, `/status`, `/metrics`, `/actuator`, `/actuator/env`, `/.env`, `/db-connect`
- Secret Indicators (detect if ≥2 present):
  - "password", "passwd", "secret", "api_key", "api_token", "access_key", "private_key", "aws_secret", "aws_access", "bearer ", "authorization"

**Test 3: Verbose Error Messages**

- Rule ID: `CUSTOM-VERBOSE-001` (MEDIUM)
- Triggers: `/compute?n=abc` (type error), `/allocate?size=abc`, `/nonexistent` (404)
- Stack Trace Indicators (detect if ≥2 present):
  - "Traceback (most recent call last)", 'File "', "line ", "raise ", "Exception:", "Error:", "at com.", "at java.", "at org.", "NullPointerException", "StackTrace"

**Test 4: Timing Attack**

- Rule ID: `CUSTOM-TIMING-001` (HIGH)
- Endpoint: `/sensitive-operation?pwd={password}`
- Configuration: Test password lengths 1, 5, 10, 20, 30
- Threshold: Final time > Initial time \* 1.5
- Indicates: Lack of constant-time comparison

**Test 5: Authentication Bypass**

- Rule ID: `CUSTOM-AUTH-001` (CRITICAL)
- Endpoint: `/auth-test?token=wrong`
- Detection: Response contains "expected" AND ("bearer" OR "token")
- Indicates: Leaked credentials in error message

**Configuration:**

- Container Limits: 0.5 CPU, 256 MB
- Health check: 10 retries, 2-second delay

---

## Complete Ruleset Summary

**Total Plugins:** 12
**Total Rule Definitions:** 150+
**Tools/Frameworks Used:** 9 (Semgrep, Gitleaks, Trivy, Nuclei, OWASP ZAP, Docker, Custom patterns)

**Severity Distribution:**

- CRITICAL: 30+ rules (Gitleaks secrets, memory forensics, debug/auth bypass detection)
- HIGH: 35+ rules (Semgrep patterns, ZAP/Nuclei, timing/race conditions)
- MEDIUM: 25+ rules (Config misconfig, resource leaks, verbose errors)
- LOW/INFO: Variable (Trivy, ZAP, Nuclei context-dependent)

---

1. **Separation of Concerns**: CLI, profiler, engine, plugins, reporting are separate modules
2. **Open/Closed Principle**: Open for extension (add plugins), closed for modification (core rarely changes)
3. **Dependency Inversion**: Engine depends on abstract `ScannerPlugin`, not concrete scanners
4. **Single Responsibility**: Each plugin does one job (SAST, SCA, IaC, etc.)
5. **Defense in Depth**: Multiple layers of security (SAST, SCA, IaC, DAST, memory forensics)

The result is a **maintainable, extensible security analysis platform** suitable for enterprise CI/CD pipelines, security audits, and compliance scanning.
