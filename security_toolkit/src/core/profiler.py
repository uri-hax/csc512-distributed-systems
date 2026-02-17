from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from security_toolkit.core.models import ScanMode, TargetProfile

logger = logging.getLogger(__name__)

# Language detection: match file names or extensions to identify languages in source tree
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
# Internal helpers
# Limit depth to 3 to balance detection accuracy vs performance
def _detect_languages(root: Path, max_depth: int = 3) -> frozenset[str]:
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
    try:
        # Use Go template to extract exposed ports from Docker image metadata
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
# Public API
def profile_target(
    target: str | None = None,
    *,
    image: str | None = None,
    pid: int | None = None,
    url: str | None = None,
) -> TargetProfile:
    specified = sum(x is not None for x in (target, image, pid, url))
    if specified == 0:
        raise ValueError(
            "At least one of target (path), image, pid, or url must be provided."
        )
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
    if image is not None and target is None and pid is None:
        ports = _detect_exposed_ports(image)
        return TargetProfile(
            mode=ScanMode.RUNTIME,
            image=image,
            service_url=url,
            exposed_ports=ports,
        )
    if url is not None and image is None and target is None and pid is None:
        port = _port_from_url(url)
        return TargetProfile(
            mode=ScanMode.RUNTIME,
            service_url=url,
            exposed_ports=(port,) if port else (),
        )
    if pid is not None and target is None and image is None and url is None:
        return TargetProfile(
            mode=ScanMode.RUNTIME,
            pid=pid,
        )
    # These combinations are handled by the CLI layer which calls
    # profile_target twice (once for source, once for runtime), so
    # reaching here means the caller passed all together.
    raise ValueError(
        "Unsupported target combination. Use the CLI 'full' command "
        "for combined source + runtime scanning."
    )


def _port_from_url(url: str) -> int | None:
    parsed = urlparse(url)
    if parsed.port:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    return 80
