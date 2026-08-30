from __future__ import annotations

from .config import ProjectConfig
from .util import IceywingError, matches_any


SENSITIVE_PATTERNS = (
    ".github/workflows/*",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "uv.lock",
    "requirements*.txt",
    "scripts/*",
    "hooks/*",
    ".gitignore",
    "iceywing.toml",
    "justfile",
    "Justfile",
    "AGENTS.md",
)


def check_branch(config: ProjectConfig, branch: str, force: bool = False) -> None:
    if matches_any(branch, config.protected_branches) and not force:
        raise IceywingError(f"Protected branch '{branch}' blocks Pop Flow writes.")

    if config.allowed_branches and not matches_any(branch, config.allowed_branches) and not force:
        raise IceywingError(
            f"Branch '{branch}' is not allowed by iceywing.toml. "
            f"Allowed: {', '.join(config.allowed_branches)}"
        )


def patch_paths(text: str) -> list[str]:
    paths = []
    for line in text.splitlines():
        if not line.startswith("+++ "):
            continue
        value = line[4:].strip()
        if value == "/dev/null":
            continue
        if value.startswith("b/"):
            value = value[2:]
        paths.append(value)
    return sorted(set(paths))


def sensitive_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if matches_any(path, SENSITIVE_PATTERNS)]
