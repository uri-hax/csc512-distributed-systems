"""Plugin interface and auto-registration machinery.

Every scanner is a concrete subclass of :class:`ScannerPlugin`.  Subclasses
are automatically registered via the :class:`_PluginRegistry` metaclass and
can be discovered at runtime through :func:`get_registered_plugins`.

Example::

    class MySemgrepScanner(ScannerPlugin):
        name = "semgrep"
        scan_modes = {ScanMode.SOURCE}

        def can_handle(self, profile: TargetProfile) -> bool:
            return profile.mode == ScanMode.SOURCE

        def execute(self, profile: TargetProfile) -> list[Finding]:
            ...
"""

from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from typing import ClassVar

from security_toolkit.core.models import Finding, ScanMode, TargetProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registry metaclass
# ---------------------------------------------------------------------------


class _PluginRegistry(ABCMeta):
    """Metaclass that records every concrete :class:`ScannerPlugin` subclass
    upon definition.  Abstract bases (those that still have abstract methods)
    are silently skipped."""

    _registry: ClassVar[dict[str, type[ScannerPlugin]]] = {}

    def __init__(cls, name: str, bases: tuple, namespace: dict) -> None:
        super().__init__(name, bases, namespace)
        # Skip the base class itself and any remaining abstract classes.
        if bases and not getattr(cls, "__abstractmethods__", frozenset()):
            plugin_name: str = getattr(cls, "name", name)
            _PluginRegistry._registry[plugin_name] = cls  # type: ignore[assignment]
            logger.debug("Registered plugin: %s -> %s", plugin_name, cls)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class ScannerPlugin(metaclass=_PluginRegistry):
    """Abstract base for every scanner plugin.

    Subclass contract:
      1. Set the ``name`` class attribute (unique identifier).
      2. Set ``scan_modes`` to the set of modes this plugin supports.
      3. Implement :meth:`can_handle` to gate activation on profile data.
      4. Implement :meth:`execute` to perform the scan and return findings.
    """

    name: ClassVar[str] = ""
    scan_modes: ClassVar[set[str]] = set()

    @abstractmethod
    def can_handle(self, profile: TargetProfile) -> bool:
        """Return ``True`` if this plugin should run for *profile*."""

    @abstractmethod
    def execute(self, profile: TargetProfile) -> list[Finding]:
        """Run the scan and return a list of findings.

        Must **not** raise -- errors should be caught internally and returned
        as an empty list (with logging).
        """


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def get_registered_plugins() -> dict[str, type[ScannerPlugin]]:
    """Return a snapshot of all currently registered plugin classes."""
    return dict(_PluginRegistry._registry)


def instantiate_plugins() -> list[ScannerPlugin]:
    """Create one instance of every registered plugin class."""
    instances: list[ScannerPlugin] = []
    for name, cls in _PluginRegistry._registry.items():
        try:
            instances.append(cls())
        except Exception:
            logger.exception("Failed to instantiate plugin %s", name)
    return instances
