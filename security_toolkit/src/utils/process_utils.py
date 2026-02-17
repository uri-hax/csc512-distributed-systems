from __future__ import annotations

import logging
import os
import signal
from pathlib import Path

logger = logging.getLogger(__name__)


def pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def get_process_exe(pid: int) -> str | None:
    exe_link = Path(f"/proc/{pid}/exe")
    try:
        return str(exe_link.resolve())
    except (OSError, FileNotFoundError):
        return None


def get_process_cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        return [arg.decode(errors="replace") for arg in raw.split(b"\x00") if arg]
    except (OSError, FileNotFoundError):
        return []


def send_signal_safe(pid: int, sig: signal.Signals = signal.SIGTERM) -> bool:
    try:
        os.kill(pid, sig)
        return True
    except (OSError, ProcessLookupError):
        logger.warning("Failed to send signal %s to PID %d", sig, pid)
        return False


def which(binary: str) -> str | None:
    import shutil

    return shutil.which(binary)


def check_tool_available(name: str) -> bool:
    return which(name) is not None
