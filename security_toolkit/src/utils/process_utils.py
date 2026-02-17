"""Process and OS-level utility helpers."""

from __future__ import annotations

import logging
import os
import signal
from pathlib import Path

logger = logging.getLogger(__name__)


def pid_exists(pid: int) -> bool:
    """Return ``True`` if a process with *pid* is running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def get_process_exe(pid: int) -> str | None:
    """Return the executable path for *pid* (Linux only)."""
    exe_link = Path(f"/proc/{pid}/exe")
    try:
        return str(exe_link.resolve())
    except (OSError, FileNotFoundError):
        return None


def get_process_cmdline(pid: int) -> list[str]:
    """Return the command line for *pid* (Linux only)."""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        return [arg.decode(errors="replace") for arg in raw.split(b"\x00") if arg]
    except (OSError, FileNotFoundError):
        return []


def send_signal_safe(pid: int, sig: signal.Signals = signal.SIGTERM) -> bool:
    """Send a signal to *pid*, returning ``True`` on success."""
    try:
        os.kill(pid, sig)
        return True
    except (OSError, ProcessLookupError):
        logger.warning("Failed to send signal %s to PID %d", sig, pid)
        return False


def which(binary: str) -> str | None:
    """Cross-platform ``which`` without shutil import overhead."""
    import shutil

    return shutil.which(binary)


def check_tool_available(name: str) -> bool:
    """Return ``True`` if *name* is on ``$PATH``."""
    return which(name) is not None
