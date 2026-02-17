"""JSON report generator.

Serialises a :class:`ScanReport` to a structured, human-readable JSON file.

The default output omits noisy vendor ``raw`` blobs so the file is easy to
read and review.  Pass ``include_raw=True`` for full traceability.
"""

from __future__ import annotations

import logging
from pathlib import Path

from security_toolkit.core.models import ScanReport

logger = logging.getLogger(__name__)


def write_json_report(
    report: ScanReport,
    output_path: Path,
    *,
    include_raw: bool = False,
) -> Path:
    """Write *report* as prettified JSON to *output_path*.

    If output_path is a directory, generates report.json.
    If output_path has no suffix, adds .json extension.
    Creates parent directories if needed.  Returns the resolved path.
    """
    output_path = output_path.resolve()

    # If path is a directory, use report.json
    if output_path.is_dir() or (not output_path.suffix and not output_path.exists()):
        output_path = output_path / "report.json"
    # If path has no suffix, add .json extension
    elif not output_path.suffix:
        output_path = output_path.with_suffix(".json")
    # If already .json, use as-is (no timestamp)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report.write_json(output_path, include_raw=include_raw)
    logger.info("JSON report written to %s", output_path)
    return output_path
