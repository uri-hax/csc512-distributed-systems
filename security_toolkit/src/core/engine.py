from __future__ import annotations

import importlib
import logging
import pkgutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Sequence

import security_toolkit.scanners as _scanners_pkg
from security_toolkit.core.models import ScanReport, TargetProfile
from security_toolkit.core.plugin import ScannerPlugin, instantiate_plugins

logger = logging.getLogger(__name__)

# Recursively import all scanner modules to trigger metaclass registration
def _import_all_plugins() -> None:
    for importer, modname, ispkg in pkgutil.walk_packages(
        _scanners_pkg.__path__,
        prefix=_scanners_pkg.__name__ + ".",
    ):
        try:
            importlib.import_module(modname)
        except Exception:
            logger.warning("Failed to import plugin module %s", modname, exc_info=True)
# Engine
class ScanEngine:
    def __init__(self, *, max_workers: int = 4) -> None:
        self.max_workers = max_workers
        # Trigger plugin registration by importing all scanner modules
        _import_all_plugins()
        self._plugins: list[ScannerPlugin] = instantiate_plugins()
        logger.info(
            "ScanEngine initialised with %d plugin(s): %s",
            len(self._plugins),
            [p.name for p in self._plugins],
        )
    # Core run loop
    def run(self, profile: TargetProfile) -> ScanReport:
        report = ScanReport(
            target=str(profile.path or profile.image or profile.pid),
            mode=profile.mode,
        )

        applicable = self._select_plugins(profile)

        # Track all plugins with their availability status
        all_plugins_status: dict[str, dict[str, object]] = {}
        for plugin in self._plugins:
            if profile.mode not in plugin.scan_modes:
                all_plugins_status[plugin.name] = {
                    "status": "skipped",
                    "reason": f"Plugin not applicable for {profile.mode} mode",
                    "findings_count": 0,
                }
            elif plugin not in applicable:
                all_plugins_status[plugin.name] = {
                    "status": "skipped",
                    "reason": "Plugin.can_handle() returned False for target",
                    "findings_count": 0,
                }

        if not applicable:
            logger.warning("No plugins applicable for profile: %s", profile)
            report.errors.append("No applicable plugins found for this target.")
            report.plugin_execution = all_plugins_status
            report.finished_at = datetime.now(timezone.utc).isoformat()
            return report

        logger.info(
            "Running %d plugin(s): %s",
            len(applicable),
            [p.name for p in applicable],
        )

        report = self._execute_parallel(applicable, profile, report)

        # Merge skipped plugin status with execution results (preserve execution status over skipped)
        for plugin_name, status in all_plugins_status.items():
            if plugin_name not in report.plugin_execution:
                report.plugin_execution[plugin_name] = status

        report.deduplicate()
        report.sort_by_severity()
        report.finished_at = datetime.now(timezone.utc).isoformat()
        return report
    # Internals
    def _select_plugins(self, profile: TargetProfile) -> list[ScannerPlugin]:
        result: list[ScannerPlugin] = []
        for plugin in self._plugins:
            if profile.mode not in plugin.scan_modes:
                continue
            try:
                if plugin.can_handle(profile):
                    result.append(plugin)
            except Exception:
                logger.exception("Error in %s.can_handle()", plugin.name)
        return result

    def _execute_parallel(
        self,
        plugins: Sequence[ScannerPlugin],
        profile: TargetProfile,
        report: ScanReport,
    ) -> ScanReport:
        # Use ThreadPoolExecutor (not ProcessPoolExecutor) because plugins are I/O-bound,
        # shelling out to external tools like semgrep, trivy, nuclei
        # Track plugin execution status
        plugin_status: dict[str, dict[str, object]] = {}
        for plugin in plugins:
            plugin_status[plugin.name] = {
                "status": "running",
                "findings_count": 0,
                "error": None,
            }

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._run_plugin, p, profile): p for p in plugins}
            for future in as_completed(futures):
                plugin = futures[future]
                try:
                    findings = future.result()
                    report.findings.extend(findings)
                    plugin_status[plugin.name]["status"] = "success"
                    plugin_status[plugin.name]["findings_count"] = len(findings)
                    logger.info(
                        "Plugin %s returned %d finding(s)", plugin.name, len(findings)
                    )
                except Exception as exc:
                    msg = f"Plugin {plugin.name} failed: {exc}"
                    logger.error(msg, exc_info=True)
                    plugin_status[plugin.name]["status"] = "failed"
                    plugin_status[plugin.name]["error"] = str(exc)
                    report.errors.append(msg)

        report.plugin_execution = plugin_status
        return report

    @staticmethod
    def _run_plugin(plugin: ScannerPlugin, profile: TargetProfile):
        logger.info("Starting plugin: %s", plugin.name)
        return plugin.execute(profile)
