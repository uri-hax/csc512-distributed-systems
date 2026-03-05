# Memory forensics scanner: analyzes process memory for secrets
# Dependencies: volatility or similar memory analysis tools
from __future__ import annotations

import logging
import math
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import ClassVar

from security_toolkit.core.models import (
    Finding,
    NormalizedSeverity,
    ScanMode,
    TargetProfile,
)
from security_toolkit.core.plugin import ScannerPlugin
from security_toolkit.core.sandbox import (
    IsolatedNetwork,
    create_isolated_network,
    remove_isolated_network,
    run_container_sandboxed,
    stop_and_remove_container,
)
from security_toolkit.utils.docker_utils import docker_available

logger = logging.getLogger(__name__)
# Secret patterns
_SECRET_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("MEM-SECRET-001", "AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "MEM-SECRET-002",
        "AWS Secret Key",
        re.compile(
            r"(?:aws_secret_access_key|secret)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})"
        ),
    ),
    (
        "MEM-SECRET-003",
        "Generic API Key",
        re.compile(
            r"(?:api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})",
            re.IGNORECASE,
        ),
    ),
    (
        "MEM-SECRET-004",
        "Generic Password",
        re.compile(
            r"(?:password|passwd|pwd)['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})",
            re.IGNORECASE,
        ),
    ),
    (
        "MEM-SECRET-005",
        "Connection String",
        re.compile(
            r"(?:mysql|postgres|mongodb|redis|amqp)://[^\s]{10,}", re.IGNORECASE
        ),
    ),
    (
        "MEM-SECRET-006",
        "Private Key Block",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    ),
    (
        "MEM-SECRET-007",
        "Bearer Token",
        re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    ),
    ("MEM-SECRET-008", "GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}")),
    ("MEM-SECRET-009", "Slack Token", re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}")),
    (
        "MEM-SECRET-010",
        "JWT Token",
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ),
    (
        "MEM-SECRET-011",
        "Google Cloud API Key",
        re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    ),
    (
        "MEM-SECRET-012",
        "Stripe Secret Key",
        re.compile(r"sk_live_[0-9a-zA-Z]{24,}"),
    ),
    (
        "MEM-SECRET-013",
        "Stripe Publishable Key",
        re.compile(r"pk_live_[0-9a-zA-Z]{24,}"),
    ),
    (
        "MEM-SECRET-014",
        "SendGrid API Key",
        re.compile(r"SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}"),
    ),
    (
        "MEM-SECRET-015",
        "Mailchimp API Key",
        re.compile(r"[0-9a-f]{32}-us[0-9]{1,2}"),
    ),
    (
        "MEM-SECRET-016",
        "Twilio API Key",
        re.compile(r"SK[0-9a-fA-F]{32}"),
    ),
    (
        "MEM-SECRET-017",
        "HashiCorp Vault Token",
        re.compile(r"hvs\.[A-Za-z0-9_\-]{24,}"),
    ),
    (
        "MEM-SECRET-018",
        "Heroku API Key",
        re.compile(
            r"(?:HEROKU|heroku).*[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        ),
    ),
    (
        "MEM-SECRET-019",
        "PEM Certificate",
        re.compile(r"-----BEGIN CERTIFICATE-----"),
    ),
    (
        "MEM-SECRET-020",
        "Hex-Encoded Secret",
        re.compile(
            r"(?:secret|token|key)['\"]?\s*[:=]\s*['\"]?[0-9a-f]{64}",
            re.IGNORECASE,
        ),
    ),
]


def _shannon_entropy(data: str) -> float:
    if not data:
        return 0.0
    freq: dict[str, int] = {}
    for ch in data:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())
# Plugin
class MemoryForensicsScanner(ScannerPlugin):
    name: ClassVar[str] = "memory-forensics"
    scan_modes: ClassVar[set[str]] = {ScanMode.RUNTIME}

    # Check if this scanner can run for the given target
    def can_handle(self, profile: TargetProfile) -> bool:
        if profile.image is None:
            return False
        if not docker_available():
            logger.warning("Docker daemon not available -- skipping memory forensics")
            return False
        return True

    # Run the scan and return findings
    def execute(self, profile: TargetProfile) -> list[Finding]:
        assert profile.image is not None
        network: IsolatedNetwork | None = None
        container_name: str | None = None

        try:
            # 1. Create isolated network
            network = create_isolated_network()

            # 2. Start target in sandbox with SYS_PTRACE for /proc/1/mem access
            info = run_container_sandboxed(
                profile.image,
                network,
                detach=True,
                read_only=False,
                memory="512m",
                cpus="0.5",
                extra_args=["--cap-add", "SYS_PTRACE"],
            )
            container_name = info["container_name"]
            if info["returncode"] != 0:
                logger.error("Failed to start container: %s", info["stderr"])
                return []

            # 3. Wait for main process to initialise
            logger.info("Waiting for container %s to initialise...", container_name)
            if not self._wait_for_container(container_name):
                logger.warning("Container %s PID 1 not ready after timeout", container_name)
                return []

            # 4. Dump memory and scan
            findings = self._dump_and_scan(container_name, profile.image)
            return findings

        except Exception:
            logger.exception("Memory forensics failed")
            return []
        finally:
            if container_name:
                stop_and_remove_container(container_name)
            if network:
                remove_isolated_network(network)
    def _wait_for_container(self, container: str, timeout: int = 15) -> bool:
        for _ in range(timeout):
            try:
                result = subprocess.run(
                    [
                        "docker", "inspect",
                        "--format", "{{.State.Running}}",
                        container,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and "true" in result.stdout.strip().lower():
                    time.sleep(2)  # settle time after container confirmed running
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False
    def _dump_and_scan(self, container: str, image: str) -> list[Finding]:
        with tempfile.TemporaryDirectory(prefix="sectoolkit_mem_") as tmpdir:
            dump_path = Path(tmpdir) / "strings.txt"
            raw_strings = ""

            # Tier 1: Try /proc access inside the container
            try:
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container,
                        "sh",
                        "-c",
                        # Read maps for context
                        "cat /proc/1/maps 2>/dev/null; "
                        # Try strings if available, otherwise use python/grep
                        "if command -v strings >/dev/null 2>&1; then "
                        "  strings /proc/1/mem 2>/dev/null; "
                        "else "
                        "  python3 -c \""
                        "import re,sys\n"
                        "try:\n"
                        "  maps=open('/proc/1/maps').readlines()\n"
                        "  mem=open('/proc/1/mem','rb')\n"
                        "  for line in maps:\n"
                        "    parts=line.split()\n"
                        "    addrs=parts[0].split('-')\n"
                        "    start,end=int(addrs[0],16),int(addrs[1],16)\n"
                        "    if end-start>10*1024*1024: continue\n"
                        "    if len(parts)>1 and 'r' not in parts[1]: continue\n"
                        "    try:\n"
                        "      mem.seek(start)\n"
                        "      data=mem.read(end-start)\n"
                        "      for m in re.finditer(rb'[\\x20-\\x7e]{6,}',data):\n"
                        "        sys.stdout.write(m.group().decode('ascii','ignore')+'\\n')\n"
                        "    except: pass\n"
                        "except: pass"
                        "\" 2>/dev/null; "
                        "fi; "
                        # Also grab environment variables
                        "cat /proc/1/environ 2>/dev/null | tr '\\0' '\\n'; "
                        "cat /proc/1/cmdline 2>/dev/null | tr '\\0' ' '",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                raw_strings = result.stdout
                logger.info(
                    "Tier 1 (/proc access): extracted %d bytes", len(raw_strings)
                )
            except Exception:
                logger.debug("Tier 1 /proc access failed")

            # Tier 2: docker exec env (always run -- additive extraction)
            try:
                result = subprocess.run(
                    ["docker", "exec", container, "env"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                raw_strings += "\n" + result.stdout
                logger.info(
                    "Tier 2 (env command): extracted %d bytes",
                    len(result.stdout),
                )
            except Exception:
                logger.debug("Tier 2 env command failed")

            # Tier 3: docker inspect (host-side, always works)
            try:
                result = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        "{{json .Config.Env}}",
                        container,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0 and result.stdout.strip():
                    import json as _json

                    env_list = _json.loads(result.stdout.strip())
                    env_text = "\n".join(env_list) if isinstance(env_list, list) else ""
                    raw_strings += "\n" + env_text
                    logger.info(
                        "Tier 3 (docker inspect): extracted %d env vars",
                        len(env_list) if isinstance(env_list, list) else 0,
                    )
            except Exception:
                logger.debug("Tier 3 docker inspect failed")

            if not raw_strings.strip():
                logger.info("No strings extracted from container memory")
                return []

            # Deduplicate lines from all tiers
            unique_lines = list(dict.fromkeys(
                line for line in raw_strings.splitlines() if line.strip()
            ))
            raw_strings = "\n".join(unique_lines)

            dump_path.write_text(raw_strings, encoding="utf-8", errors="replace")
            logger.info(
                "Total extracted: %d unique lines (%d bytes) from container %s",
                len(unique_lines),
                len(raw_strings),
                container,
            )

            return self._scan_strings(raw_strings, image)

    def _scan_strings(self, raw: str, source: str) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[str] = set()

        for rule_id, description, pattern in _SECRET_PATTERNS:
            for match in pattern.finditer(raw):
                matched_text = match.group(0)
                # Avoid reporting the same literal twice
                key = f"{rule_id}:{matched_text[:40]}"
                if key in seen:
                    continue
                seen.add(key)

                # Redact the actual secret value for the report
                redacted = (
                    matched_text[:6] + "..." + matched_text[-4:]
                    if len(matched_text) > 12
                    else "***REDACTED***"
                )

                findings.append(
                    Finding(
                        tool="memory-forensics",
                        rule_id=rule_id,
                        title=f"Runtime secret detected: {description}",
                        description=f"Cleartext secret found in process memory of image {source}. Pattern: {description}. Value (redacted): {redacted}",
                        severity=NormalizedSeverity.CRITICAL,
                        file_path=f"memory://{source}",
                        category="memory",
                        raw={"pattern": description, "redacted_match": redacted},
                    )
                )

        # High-entropy string detection (likely tokens/keys)
        _FP_PREFIXES = ("PATH=", "HOME=", "LANG=", "TERM=", "HOSTNAME=", "SHLVL=")
        for line in raw.split("\n"):
            line = line.strip()
            if len(line) < 20 or len(line) > 200:
                continue
            # Skip common environment variable false positives
            if any(line.startswith(p) for p in _FP_PREFIXES):
                continue
            entropy = _shannon_entropy(line)
            if entropy > 5.0 and re.match(r"^[A-Za-z0-9+/=_\-.:]{20,}$", line):
                key = f"HI-ENTROPY:{line[:30]}"
                if key in seen:
                    continue
                seen.add(key)
                redacted = line[:6] + "..." + line[-4:]
                findings.append(
                    Finding(
                        tool="memory-forensics",
                        rule_id="MEM-ENTROPY-001",
                        title="High-entropy string in process memory",
                        description=f"A high-entropy string (Shannon={entropy:.2f}) was found in memory, potentially a secret or token. Value (redacted): {redacted}",
                        severity=NormalizedSeverity.HIGH,
                        file_path=f"memory://{source}",
                        category="memory",
                        raw={"entropy": entropy, "redacted_match": redacted},
                    )
                )

        return findings
