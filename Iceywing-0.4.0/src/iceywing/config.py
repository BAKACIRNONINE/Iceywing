from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectConfig:
    root: Path
    name: str
    environment_type: str = "auto"
    runtimes: list[str] = field(default_factory=list)
    isolated: bool = True
    tasks: dict[str, str] = field(default_factory=dict)
    protected_branches: list[str] = field(default_factory=lambda: ["main", "master"])
    allowed_branches: list[str] = field(default_factory=list)
    delete_patch_after_success: bool = True
    push_default: bool = False
    verify_baseline: bool = False


def load_config(root: Path) -> ProjectConfig:
    path = root / "iceywing.toml"
    if not path.exists():
        return ProjectConfig(root=root, name=root.name)

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    env = data.get("environment", {})
    tasks = data.get("tasks", {})
    git = data.get("git", {})
    pop = data.get("pop", {})

    return ProjectConfig(
        root=root,
        name=str(project.get("name", root.name)),
        environment_type=str(env.get("type", "auto")),
        runtimes=[str(v) for v in env.get("runtimes", [])],
        isolated=bool(env.get("isolated", True)),
        tasks={str(k): str(v) for k, v in tasks.items()},
        protected_branches=[str(v) for v in git.get("protected_branches", ["main", "master"])],
        allowed_branches=[str(v) for v in git.get("allowed_branches", [])],
        delete_patch_after_success=bool(pop.get("delete_patch_after_success", True)),
        push_default=bool(pop.get("push_default", False)),
        verify_baseline=bool(pop.get("verify_baseline", False)),
    )
