from __future__ import annotations

from pathlib import Path

from . import environment, popflow
from .config import ProjectConfig, load_config
from .project import find_project_root


class Project:
    """Small Python API over the same project operations used by the CLI."""

    def __init__(self, root: str | Path = ".") -> None:
        self.root = find_project_root(Path(root))
        self.config: ProjectConfig = load_config(self.root)

    @property
    def name(self) -> str:
        return self.config.name

    def doctor(self) -> bool:
        return environment.doctor(self.config)

    def up(self) -> None:
        environment.up(self.config)

    def run(self) -> None:
        environment.run_project(self.config)

    def stop(self) -> None:
        environment.stop_project(self.config)

    def verify(self) -> None:
        environment.verify(self.config)

    def pop_apply(self, patch: str | Path, **kwargs) -> None:
        popflow.apply(self.config, Path(patch), **kwargs)

    def pop_push(self, *, dry_run: bool = False) -> None:
        popflow.push(self.config, dry_run=dry_run)
