from dataclasses import dataclass

@dataclass
class BuildResult:
    success: bool
    run_cmd: list | None
    stdout: str
    stderr: str