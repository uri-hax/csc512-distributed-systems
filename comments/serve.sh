#!/usr/bin/env bash
set -euo pipefail

# Only run inside a container
if [ -f "/.dockerenv" ] || ( [ -r /proc/1/cgroup ] && grep -qaE 'docker|kubepods|containerd' /proc/1/cgroup ); then
  :
else
  printf '%s\n' "{\"error\":\"must_run_in_container\",\"message\":\"This script must be executed inside the Docker container.\"}" >&2
  exit 1
fi

# Require SUBMISSIONS_ROOT to be provided by the runtime
if [ -z "${SUBMISSIONS_ROOT:-}" ]; then
  printf '%s\n' "{\"error\":\"missing_SUBMISSIONS_ROOT\",\"message\":\"Set SUBMISSIONS_ROOT environment variable when running the container.\"}" >&2
  exit 1
fi

mkdir -p "$SUBMISSIONS_ROOT"
exec uvicorn 'app.main:app' --host=0.0.0.0 --port=80
