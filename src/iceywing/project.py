from __future__ import annotations

from pathlib import Path

from .config import ProjectConfig, load_config
from .util import IceywingError


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).expanduser().resolve()
    if not current.exists():
        raise IceywingError(f"Project path does not exist: {current}")
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (candidate / "iceywing.toml").exists() or (candidate / ".git").exists():
            return candidate

    markers = ("package.json", "pyproject.toml", "Cargo.toml", "justfile", "Justfile")
    if any((current / marker).exists() for marker in markers):
        return current

    raise IceywingError(
        f"No Iceywing project found.\nCurrent: {current}\n"
        "Run inside a project or pass its path: `iceywing up <path>`."
    )


def current_project(start: Path | None = None) -> ProjectConfig:
    root = find_project_root(start)
    return load_config(root)
