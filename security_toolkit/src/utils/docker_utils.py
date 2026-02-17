from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def image_exists(image: str) -> bool:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode == 0


def pull_image(image: str, *, timeout: int = 300) -> bool:
    logger.info("Pulling image: %s", image)
    result = subprocess.run(
        ["docker", "pull", image],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode == 0


def inspect_image(image: str) -> dict[str, Any]:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker inspect failed: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    return data[0] if isinstance(data, list) else data


def get_image_digest(image: str) -> str:
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{index .RepoDigests 0}}", image],
        capture_output=True,
        text=True,
        timeout=15,
    )
    digest = result.stdout.strip()
    if not digest or result.returncode != 0:
        # Fallback to image ID
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Id}}", image],
            capture_output=True,
            text=True,
            timeout=15,
        )
        digest = result.stdout.strip()
    return digest


def exec_in_container(container: str, cmd: list[str], *, timeout: int = 60) -> str:
    result = subprocess.run(
        ["docker", "exec", container] + cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        logger.warning("docker exec failed in %s: %s", container, result.stderr.strip())
    return result.stdout
