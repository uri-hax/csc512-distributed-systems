from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from typing import ClassVar

from security_toolkit.core.models import Finding, ScanMode, TargetProfile

logger = logging.getLogger(__name__)


class _PluginRegistry(ABCMeta):
    _registry: ClassVar[dict[str, type[ScannerPlugin]]] = {}

    def __init__(cls, name: str, bases: tuple, namespace: dict) -> None:
        super().__init__(name, bases, namespace)
        # Skip the base class itself and any remaining abstract classes.
        if bases and not getattr(cls, "__abstractmethods__", frozenset()):
            plugin_name: str = getattr(cls, "name", name)
            _PluginRegistry._registry[plugin_name] = cls  # type: ignore[assignment]
            logger.debug("Registered plugin: %s -> %s", plugin_name, cls)


class ScannerPlugin(metaclass=_PluginRegistry):
    name: ClassVar[str] = ""
    scan_modes: ClassVar[set[str]] = set()

    @abstractmethod
    def can_handle(self, profile: TargetProfile) -> bool:
        pass

    @abstractmethod
    def execute(self, profile: TargetProfile) -> list[Finding]:
        pass


def get_registered_plugins() -> dict[str, type[ScannerPlugin]]:
    return dict(_PluginRegistry._registry)


def instantiate_plugins() -> list[ScannerPlugin]:
    instances: list[ScannerPlugin] = []
    for name, cls in _PluginRegistry._registry.items():
        try:
            instances.append(cls())
        except Exception:
            logger.exception("Failed to instantiate plugin %s", name)
    return instances
