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

if [ -z "${LLM_MODEL:-}" ]; then
  printf '%s\n' "{\"error\":\"missing_LLM_MODEL\",\"message\":\"Set LLM_MODEL environment variable when running the container.\"}" >&2
  exit 1
fi

ollama serve > /tmp/ollama.log 2>&1 &
OLLAMA_PID=$!

# Verify LLM is available before starting the API
for i in {1..20}; do
  if curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# If Ollama didn't start, exit
if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
  printf '%s\n' "{\"error\":\"failed_to_start\",\"message\":\"Service did not start correctly.\"}" >&2
  exit 1
fi

ollama pull "$LLM_MODEL"
exec uvicorn 'app.main:app' --host=0.0.0.0 --port=80 --timeout-keep-alive=300
