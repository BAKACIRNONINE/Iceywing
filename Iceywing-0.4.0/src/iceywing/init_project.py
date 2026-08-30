from __future__ import annotations

import json
from pathlib import Path

from .util import IceywingError


CONFIG = """\
[project]
name = "{name}"

[environment]
runtimes = ["{env_type}"]
isolated = true

[tasks]
setup = "just setup"
run = "just run"
verify = "just verify"
doctor = "just doctor"
clean = "just clean"

[git]
protected_branches = ["main", "master"]
allowed_branches = []

[pop]
delete_patch_after_success = true
push_default = false
verify_baseline = false
"""


def detect(root: Path) -> str:
    if (root / "package.json").exists():
        return "node"
    if (root / "pyproject.toml").exists():
        return "python"
    if (root / "Cargo.toml").exists():
        return "rust"
    return "generic"


def node_justfile(root: Path) -> str:
    package = {}
    try:
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except Exception:
        pass

    scripts = package.get("scripts", {})
    lines = []

    lines += [
        "setup:",
        "    npm ci" if (root / "package-lock.json").exists() else "    npm install",
        "",
    ]

    if "dev" in scripts:
        lines += ["run:", "    npm run dev", ""]
    elif "start" in scripts:
        lines += ["run:", "    npm start", ""]

    lines += [
        "doctor:",
        "    node --version",
        "    npm --version",
        "    just --version",
        "",
    ]

    available = []
    for name in ["typecheck", "test", "lint", "build"]:
        if name in scripts:
            cmd = "npm test" if name == "test" else f"npm run {name}"
            lines += [f"{name}:", f"    {cmd}", ""]
            available.append(name)

    if available:
        lines += ["verify:"]
        lines += [f"    just {name}" for name in available]
        lines += [""]

    return "\n".join(lines)


def init(root: Path, force: bool = False) -> None:
    root = root.resolve()
    env_type = detect(root)
    config = root / "iceywing.toml"
    justfile = root / "justfile"

    if config.exists() and not force:
        raise IceywingError("iceywing.toml already exists. Use --force to replace it.")

    config.write_text(CONFIG.format(name=root.name, env_type=env_type), encoding="utf-8")

    if not justfile.exists():
        if env_type == "node":
            justfile.write_text(node_justfile(root), encoding="utf-8")
        elif env_type == "python":
            justfile.write_text(
                """setup:
    uv sync

test:
    uv run pytest

verify:
    just test

doctor:
    python --version
    uv --version
    just --version

clean:
    echo "Define safe project cleanup before using this recipe."
    exit 1
""",
                encoding="utf-8",
            )
        else:
            justfile.write_text(
                """doctor:
    just --version
""",
                encoding="utf-8",
            )

    print("[OK] iceywing.toml")
    print("[OK] justfile")
    print("\nReview branch rules and task recipes before Pop Flow writes.")
