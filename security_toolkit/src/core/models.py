from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any
# Severity
class NormalizedSeverity(IntEnum):
    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


# Lookup table: lowercase vendor label -> NormalizedSeverity
_SEVERITY_MAP: dict[str, NormalizedSeverity] = {
    # Trivy / Grype
    "unknown": NormalizedSeverity.INFO,
    "negligible": NormalizedSeverity.INFO,
    "low": NormalizedSeverity.LOW,
    "medium": NormalizedSeverity.MEDIUM,
    "high": NormalizedSeverity.HIGH,
    "critical": NormalizedSeverity.CRITICAL,
    # Semgrep
    "info": NormalizedSeverity.INFO,
    "warning": NormalizedSeverity.MEDIUM,
    "error": NormalizedSeverity.HIGH,
    # Nuclei
    "informative": NormalizedSeverity.INFO,
    # Generic fallbacks
    "moderate": NormalizedSeverity.MEDIUM,
    "important": NormalizedSeverity.HIGH,
}


def normalize_severity(raw: str) -> NormalizedSeverity:
    return _SEVERITY_MAP.get(raw.strip().lower(), NormalizedSeverity.MEDIUM)
# Scan mode
class ScanMode:
    SOURCE = "source"
    RUNTIME = "runtime"
    FULL = "full"
# Target profile
@dataclass(frozen=True)
class TargetProfile:
    mode: str
    path: Path | None = None
    image: str | None = None
    pid: int | None = None
    service_url: str | None = None
    languages: frozenset[str] = field(default_factory=frozenset)
    has_docker: bool = False
    has_k8s: bool = False
    has_terraform: bool = False
    exposed_ports: tuple[int, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
# Finding
@dataclass
class Finding:
    tool: str
    rule_id: str
    title: str
    description: str
    severity: NormalizedSeverity
    file_path: str | None = None
    line: int = 0
    category: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.fingerprint:
            self.fingerprint = self._compute_fingerprint()
    def _compute_fingerprint(self) -> str:
        blob = f"{self.rule_id}|{self.file_path}|{self.line}|{self.title}"
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        location = self.file_path or ""
        if self.line:
            location += f":{self.line}"
        d: dict[str, Any] = {
            "severity": self.severity.name,
            "tool": self.tool,
            "rule_id": self.rule_id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "location": location,
            "fingerprint": self.fingerprint,
        }
        if include_raw and self.raw:
            d["raw"] = self.raw
        return d
# Scan report
@dataclass
class ScanReport:
    target: str
    mode: str
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    finished_at: str = ""
    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    plugin_execution: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Deduplication
    def deduplicate(self) -> None:
        seen: dict[str, Finding] = {}
        for f in self.findings:
            existing = seen.get(f.fingerprint)
            if existing is None or f.severity > existing.severity:
                seen[f.fingerprint] = f
        self.findings = list(seen.values())
    # Sorting
    def sort_by_severity(self) -> None:
        self.findings.sort(key=lambda f: f.severity, reverse=True)
    # Summaries
    def severity_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {s.name: 0 for s in NormalizedSeverity}
        for f in self.findings:
            counts[f.severity.name] += 1
        return counts
    # Serialisation
    def to_json(self, *, indent: int = 2, include_raw: bool = False) -> str:
        # Group findings by category
        grouped: dict[str, list[dict[str, Any]]] = {}
        for f in self.findings:
            cat = f.category or "other"
            grouped.setdefault(cat, []).append(
                f.to_dict(include_raw=include_raw)
            )

        # Build plugin execution summary lists
        executed_plugins: list[dict[str, Any]] = []
        failed_plugins: list[dict[str, Any]] = []
        skipped_plugins: list[dict[str, Any]] = []
        for name, info in self.plugin_execution.items():
            entry: dict[str, Any] = {"plugin": name}
            status = info.get("status", "unknown")
            if status == "success":
                entry["findings_count"] = info.get("findings_count", 0)
                executed_plugins.append(entry)
            elif status == "failed":
                entry["error"] = info.get("error", "Unknown error")
                failed_plugins.append(entry)
            elif status == "skipped":
                entry["reason"] = info.get("reason", "Unknown reason")
                skipped_plugins.append(entry)

        data = {
            "report": {
                "target": self.target,
                "mode": self.mode,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "verdict": self._verdict(),
            },
            "summary": {
                "total_findings": len(self.findings),
                "by_severity": self.severity_counts(),
            },
            "plugins": {
                "total_registered": len(self.plugin_execution),
                "executed": {
                    "count": len(executed_plugins),
                    "plugins": executed_plugins,
                },
                "failed": {
                    "count": len(failed_plugins),
                    "plugins": failed_plugins,
                },
                "skipped": {
                    "count": len(skipped_plugins),
                    "plugins": skipped_plugins,
                },
            },
            "findings_by_category": grouped,
            "errors": self.errors if self.errors else [],
        }
        return json.dumps(data, indent=indent, default=str, ensure_ascii=False)

    def _verdict(self) -> str:
        if any(f.severity >= NormalizedSeverity.HIGH for f in self.findings):
            return "FAIL"
        if self.findings:
            return "WARN"
        return "PASS"

    def write_json(self, path: Path, *, include_raw: bool = False) -> None:
        path.write_text(
            self.to_json(include_raw=include_raw), encoding="utf-8"
        )
