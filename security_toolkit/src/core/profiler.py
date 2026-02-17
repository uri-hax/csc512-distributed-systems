"""Target profiler -- inspects the supplied target and produces a
:class:`TargetProfile` that drives plugin selection.

Detection heuristics:
  * **Source mode** -- target is an existing directory.  Languages are
    identified by the presence of well-known manifest / lock files.
  * **Runtime mode** -- target looks like a Docker image reference
    (contains ``:``) or is a numeric PID.
  * **URL mode** -- a ``--url`` is provided pointing at a running service.
    HTTP-based runtime plugins connect directly instead of starting a
    container.  Can be combined with ``--image`` so Docker-specific
    plugins (container-scanner, memory-forensics, drift-detector) still
    run.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from security_toolkit.core.models import ScanMode, TargetProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language detection table
# ---------------------------------------------------------------------------

# Mapping: language name -> set of file names or glob suffixes that indicate
# the language is present.  We search the top two directory levels.

_LANGUAGE_INDICATORS: dict[str, set[str]] = {
    "python": {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "Pipfile.lock",
        "requirements.txt",
        "poetry.lock",
        "*.py",
    },
    "javascript": {
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "*.js",
        "*.jsx",
        "*.mjs",
        "*.cjs",
    },
    "typescript": {
        "tsconfig.json",
        "*.ts",
        "*.tsx",
    },
    "go": {
        "go.mod",
        "go.sum",
        "*.go",
    },
    "rust": {
        "Cargo.toml",
        "Cargo.lock",
        "*.rs",
    },
    "c": {
        "*.c",
        "*.h",
        "Makefile",
        "CMakeLists.txt",
    },
    "cpp": {
        "*.cpp",
        "*.cc",
        "*.cxx",
        "*.hpp",
    },
    "java": {
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "*.java",
    },
    "ruby": {
        "Gemfile",
        "Gemfile.lock",
        "*.rb",
    },
    "php": {
        "composer.json",
        "composer.lock",
        "*.php",
    },
    "csharp": {
        "*.csproj",
        "*.sln",
        "*.cs",
    },
    "kotlin": {
        "*.kt",
        "*.kts",
    },
    "scala": {
        "*.scala",
        "build.sbt",
    },
    "swift": {
        "*.swift",
        "Package.swift",
    },
    "bash": {
        "*.sh",
        "*.bash",
    },
    "dart": {
        "*.dart",
        "pubspec.yaml",
    },
    "elixir": {
        "*.ex",
        "*.exs",
        "mix.exs",
    },
    "haskell": {
        "*.hs",
        "stack.yaml",
        "*.cabal",
    },
    "lua": {
        "*.lua",
    },
    "perl": {
        "*.pl",
        "*.pm",
    },
    "r": {
        "*.R",
        "*.r",
        "DESCRIPTION",
    },
    "objective-c": {
        "*.m",
        "*.mm",
    },
    "powershell": {
        "*.ps1",
        "*.psm1",
    },
    "groovy": {
        "*.groovy",
        "Jenkinsfile",
    },
    "terraform": {
        "*.tf",
        "*.tfvars",
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_languages(root: Path, max_depth: int = 3) -> frozenset[str]:
    """Walk *root* up to *max_depth* levels and match against indicator
    patterns.  Returns a frozenset of detected language names."""
    detected: set[str] = set()

    def _scan(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = list(directory.iterdir())
        except PermissionError:
            return
        for entry in entries:
            name = entry.name
            for lang, indicators in _LANGUAGE_INDICATORS.items():
                if lang in detected:
                    continue
                for pattern in indicators:
                    if pattern.startswith("*"):
                        if name.endswith(pattern[1:]):
                            detected.add(lang)
                            break
                    elif name == pattern:
                        detected.add(lang)
                        break
            if entry.is_dir() and not name.startswith("."):
                _scan(entry, depth + 1)

    _scan(root, 0)
    return frozenset(detected)


def _has_file(root: Path, names: set[str], max_depth: int = 3) -> bool:
    """Return ``True`` if any file matching *names* exists under *root*."""

    def _scan(directory: Path, depth: int) -> bool:
        if depth > max_depth:
            return False
        try:
            entries = list(directory.iterdir())
        except PermissionError:
            return False
        for entry in entries:
            if entry.name in names:
                return True
            if entry.is_dir() and not entry.name.startswith("."):
                if _scan(entry, depth + 1):
                    return True
        return False

    return _scan(root, 0)


def _detect_exposed_ports(image: str) -> tuple[int, ...]:
    """Inspect a Docker image for EXPOSE directives."""
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{range $p, $conf := .Config.ExposedPorts}}{{$p}} {{end}}",
                image,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return ()
        ports: list[int] = []
        for token in result.stdout.strip().split():
            match = re.match(r"(\d+)", token)
            if match:
                ports.append(int(match.group(1)))
        return tuple(sorted(ports))
    except Exception:
        logger.debug("Could not inspect image %s for ports", image, exc_info=True)
        return ()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def profile_target(
    target: str | None = None,
    *,
    image: str | None = None,
    pid: int | None = None,
    url: str | None = None,
) -> TargetProfile:
    """Analyse the provided target and return a :class:`TargetProfile`.

    At least one of *target* (directory path), *image*, *pid*, or *url*
    should be provided.  *url* may be combined with *image* so that
    HTTP-based plugins use the live URL while Docker-specific plugins
    still inspect the image.

    Raises:
        ValueError: If no target is specified, or if the target cannot
            be resolved.
    """
    specified = sum(x is not None for x in (target, image, pid, url))
    if specified == 0:
        raise ValueError(
            "At least one of target (path), image, pid, or url must be provided."
        )

    # --- Source mode (directory) -------------------------------------------
    if target is not None and image is None and pid is None and url is None:
        path = Path(target).resolve()
        if not path.is_dir():
            raise ValueError(f"Target path is not a directory: {path}")
        languages = _detect_languages(path)
        return TargetProfile(
            mode=ScanMode.SOURCE,
            path=path,
            languages=languages,
            has_docker=_has_file(path, {"Dockerfile", "dockerfile", "Containerfile"}),
            has_k8s=_has_file(
                path,
                {
                    "deployment.yaml",
                    "deployment.yml",
                    "service.yaml",
                    "service.yml",
                    "kustomization.yaml",
                    "kustomization.yml",
                    "Chart.yaml",
                },
            ),
            has_terraform=_has_file(path, {"main.tf", "variables.tf", "terraform.tf"}),
        )

    # --- Runtime mode (image + optional url) ------------------------------
    if image is not None and target is None and pid is None:
        ports = _detect_exposed_ports(image)
        return TargetProfile(
            mode=ScanMode.RUNTIME,
            image=image,
            service_url=url,
            exposed_ports=ports,
        )

    # --- Runtime mode (url only, no image) --------------------------------
    if url is not None and image is None and target is None and pid is None:
        port = _port_from_url(url)
        return TargetProfile(
            mode=ScanMode.RUNTIME,
            service_url=url,
            exposed_ports=(port,) if port else (),
        )

    # --- Runtime mode (PID) -----------------------------------------------
    if pid is not None and target is None and image is None and url is None:
        return TargetProfile(
            mode=ScanMode.RUNTIME,
            pid=pid,
        )

    # --- Full mode helpers (target + image/url) ---------------------------
    # These combinations are handled by the CLI layer which calls
    # profile_target twice (once for source, once for runtime), so
    # reaching here means the caller passed all together.
    raise ValueError(
        "Unsupported target combination. Use the CLI 'full' command "
        "for combined source + runtime scanning."
    )


def _port_from_url(url: str) -> int | None:
    """Extract the port number from a URL, defaulting to 80/443."""
    parsed = urlparse(url)
    if parsed.port:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    return 80
