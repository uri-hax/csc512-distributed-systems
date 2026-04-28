# Chaos Testing for Code Submission

A chaos testing framework for student code submissions. Runs submissions inside isolated Docker containers and injects CPU, memory, and network constraints to measure how programs behave under resource pressure and produces a detailed report of any error/warning indicators.

---

## Table of Contents

1. [Requirements](#requirements)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Pipeline](#pipeline)
5. [Future Work](#future-work)

---

## Requirements

- Python 3.11+
- Docker Desktop (macOS / Windows) or Docker Engine (Linux)

### Install Python dependencies

```bash
pip install -e .
```

This installs `submission_runner` as a local editable package,
making it importable from anywhere in the project.

### Verify Docker is running

```bash
docker --version
```

### Build container images

Run the setup script once to build all language containers:

```bash
python setup_docker.py
```

This creates three images:

| Image | Language | Compiler |
|---|---|---|
| `submission-runner-python` | Python | 3.11 |
| `submission-runner-c` | C | GCC 13 |
| `submission-runner-cpp` | C++ | GCC 13 / C++17 |

> **Adding submission dependencies:** if student code imports third-party
> packages (numpy, pandas, etc.), add them to `Dockerfile.python` before
> building:
> ```dockerfile
> RUN pip install --no-cache-dir numpy pandas matplotlib scipy
> ```
> Then re-run `python setup_docker.py` to rebuild the image.

## Quick Start

Run from the parent directory

```bash
python run_chaos.py --path test_code/test.cpp
```
If no profile is indicated the default option will run all chaos profiles.
To run on a single profile:

```bash
python run_chaos.py --path test_code/test.cpp --profile memory_ceiling
```

Default timeout is set to 120s, for running a single profile or quick tests the 
recommendation is to reset the timeout flag:
```bash
python run_chaos.py --path submission.cpp --timeout 60
```

Reports will be produced in the `chaos_reports` directory with the date and timestamp.

```bash
chaos_reports/TIMESTAMP/
  report.txt      student-facing summary
  result.json     machine-readable metrics
  stdout.txt      program output per profile
  stderr.txt      error signals per profile
```

## Architecture

### runtime_chaos/

| File | Description |
|---|---|
| `run_chaos.py` | Entry point: handles single file and directory submissions, runs all chaos profiles, writes reports |
| `chaos_runner.py` | Core runner: builds the docker command, starts the chaos injection thread, polls docker stats |
| `chaos_config.py` | Profile definitions: CPU, memory, and network chaos profiles with their resource snapshots |
| `report_format.py` | Metrics parsing: parses stdout, classifies failures, generates student feedback |
| `analyze.py` | Standalone post-run analysis: reads a saved report directory and produces comparison output |
| `pyproject.toml` | Makes `submission_runner` importable as an editable package |

### submission_runner/

| File | Description |
|---|---|
| `docker_runner.py` | Runs commands in isolated Docker containers |
| `build.py` | Detects and executes the build system for a submission directory |
| `build_systems.py` | Build system implementations (make, script, single file) |
| `build_result.py` | BuildResult dataclass returned by build_submission() |
| `detect.py` | Detects build system type and runtime arguments from dirs.txt |
| `lang_reg.py` | Language registry maps extensions to compile and run commands |
| `run.py` | Runs a built submission and returns output |
| `setup_Docker.py` | Builds the three Docker images for Python, C, and C++ |
| `Dockerfile.c` | GCC 13 container for C submissions |
| `Dockerfile.cpp` | GCC 13 / C++17 container for C++ submissions |
| `Dockerfile.python` | Python 3.11 container for Python submissions |

## Pipeline

The chaos testing pipeline runs in four stages. Each stage is isolated so that
a failure in compilation stops the pipeline before any containers are run, 
and each chaos profile runs in a fresh container with no state carried 
between runs.

### 1. Submission Detection

`run_chaos.py` receives a path to either a single file or a project directory.

- **Single file** (`.c`, `.cpp`, `.py`) language is detected from the 
  extension via `lang_reg.py`. C and C++ files are compiled first using 
  `run_in_container()` with no chaos applied. The binary is passed to stage 2.
- **Directory** — handed to `build_submission()` in `submission_runner/build.py` 
  which detects the build system (Makefile, script, or single file) and 
  returns a run command. Runtime arguments are read from `dirs.txt` if present.

### 2. Baseline Run

The `none` profile always runs first regardless of which profiles are selected. 
This establishes the unconstrained baseline metrics such as wall time, peak RSS, 
and CPU usage, against which all subsequent profiles are measured.

### 3. Chaos Injection

Each remaining profile runs in sequence. For each profile `chaos_runner.py`:

1. Builds a `docker run` command with the profile's initial resource constraints 
   (`--cpus`, `--memory`) applied at container start
2. Starts a background stats thread that polls `docker stats` every 0.5 seconds, 
   capturing peak RSS, CPU percentage, and PID count
   > This polling time may not be sufficient for very short running programs, may
   > need adjusting for future implementations.
3. Starts a second background thread that fires `docker update` and `tc` commands 
   at scheduled intervals to inject dynamic constraints mid-run
4. Waits for the container to exit, timeout, or be killed
5. Signals both threads to stop and flushes collected stats into a `ChaosRunResult` dataclass


> **Testing coverage:** CPU and memory profiles have been validated on 
> macOS Docker Desktop. Network profiles (`network_degrade`, `network_flap`) 
> are implemented but require further testing. I/O chaos (`blkio_weight`) 
> is not functional on macOS.

### 4. Report Generation

After all profiles complete, `save_run_report()` in `run_chaos.py`:

1. Calls `report_format.parse_metrics()` on each profile's stdout to extract 
   program-reported throughput and memory metrics
2. Calls `compare_to_baseline()` to compute wall time and memory deltas against 
   the `none` baseline
3. Calls `report_format.generate_feedback()` to classify each result and produce 
   student-facing feedback
4. Writes four files to `chaos_reports/TIMESTAMP/`:

### Extending the Pipeline

The pipeline is designed to be modular at each stage:

- **New languages:** add an entry to `lang_reg.py` and a corresponding 
  `Dockerfile.language`. No changes required elsewhere.
- **New chaos profiles:** add a `ChaosProfile` entry to `PROFILES` in 
  `chaos_config.py`. The profile will automatically appear in `--all-profiles` 
  runs.
- **Custom reporting:** `result.json` contains the full metrics for every 
  profile run and is the intended integration point for downstream tools such 
  as Gradescope webhooks or batch analysis scripts.
- **Batch processing:** `run_chaos_on_path()` in `run_chaos.py` is importable 
  as a function. A batch runner can call it in a loop across a directory of 
  student submissions and aggregate `result.json` files for class-wide analysis.
- **Analysis and aggregation:** `analyze.py` is the intended extension point 
  for post-run analysis. Currently produces per-run comparison output with 
  planned extensions to include CSV export for class-wide aggregation, 
  instructor-facing summaries distinct from `report.txt`, and batch 
  comparison across multiple student submissions using `result.json` 
  as the common data format.

## Future Work

This tool is intended to be a starting point for future research and development.
There are several aspects either untested or unimplemented due to timing and
equipment constraints. Some future endeavors could include:

1. **Language Extension**
    - Extend funtionality to more languages and inclue additional compilers.
2. **Chaos Enhancement**
    - Test and implement network degradation and I/O chaos.
    - Redeploy on Linux and recover run-time CPU chaos profiles.
    - Expand chaos to cover more edge cases.
3. **Enhanced Reporting**
    - Complete batch submission handling to test on dozens of submissions.
    - Generate report and additional metrics to use in research work.
4. **Data Analysis**
   - Expand `result.json` to capture additional metrics suitable for 
     statistical analysis such as execution time distributions, memory 
     growth rates, and failure correlation across profiles.
   - Aggregate results across class-wide submission sets to support 
     research into the relationship between chaos sensitivity and code quality.
   - Integrate with data analysis pipelines for visualization and 
     hypothesis testing, such as whether programs that fail under 
     `cpu_tenth` are statistically more likely to fail under memory 
     constraints as well.