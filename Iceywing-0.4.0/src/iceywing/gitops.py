from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .util import IceywingError, run


@dataclass
class GitRepo:
    root: Path

    @classmethod
    def discover(cls, start: Path) -> "GitRepo":
        result = run(["git", "rev-parse", "--show-toplevel"], cwd=start, check=False)
        if result.returncode != 0:
            raise IceywingError("Git repository not detected.")
        return cls(Path((result.stdout or "").strip()).resolve())

    def branch(self) -> str:
        stdout = run(["git", "branch", "--show-current"], cwd=self.root).stdout or ""
        return stdout.strip() or "(detached)"

    def head(self) -> str:
        return (run(["git", "rev-parse", "HEAD"], cwd=self.root).stdout or "").strip()

    def status(self) -> str:
        return run(["git", "status", "--porcelain"], cwd=self.root).stdout or ""

    def clean(self) -> bool:
        return self.status().strip() == ""

    def tracked_diff(self) -> str:
        return run(["git", "diff", "--binary"], cwd=self.root).stdout or ""

    def untracked_paths(self) -> list[str]:
        output = run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=self.root,
        ).stdout or ""
        return sorted(path for path in output.split("\0") if path)

    def diff(self) -> str:
        tracked = self.tracked_diff()
        untracked = self.untracked_paths()
        if not untracked:
            return tracked
        marker = "\n".join(f"?? {path}" for path in untracked)
        return f"{tracked}\n# Untracked files\n{marker}\n"

    def diff_hash(self) -> str:
        digest = hashlib.sha256()
        digest.update(self.status().encode("utf-8"))
        digest.update(self.tracked_diff().encode("utf-8"))
        for rel in self.untracked_paths():
            path = self.root / rel
            digest.update(rel.encode("utf-8"))
            if path.is_symlink():
                digest.update(os.readlink(path).encode("utf-8"))
            elif path.is_file():
                with path.open("rb") as f:
                    for block in iter(lambda: f.read(1024 * 1024), b""):
                        digest.update(block)
        return digest.hexdigest()

    def diff_stat(self) -> str:
        tracked = (run(["git", "diff", "--stat"], cwd=self.root).stdout or "").strip()
        untracked = self.untracked_paths()
        parts = [tracked] if tracked else []
        if untracked:
            parts.append(f"Untracked files ({len(untracked)}):")
            parts.extend(f"  + {path}" for path in untracked)
        return "\n".join(parts)

    def diff_names(self) -> str:
        tracked = (run(["git", "diff", "--name-status"], cwd=self.root).stdout or "").strip()
        lines = [tracked] if tracked else []
        lines.extend(f"??\t{path}" for path in self.untracked_paths())
        return "\n".join(lines)

    def apply_check(self, patch: Path, three_way: bool = False) -> None:
        args = ["git", "apply", "--check"]
        if three_way:
            args.append("--3way")
        args.append(str(patch))
        run(args, cwd=self.root)

    def apply(self, patch: Path, three_way: bool = False) -> None:
        args = ["git", "apply"]
        if three_way:
            args.append("--3way")
        args.append(str(patch))
        run(args, cwd=self.root)

    def commit(self, message: str) -> str:
        run(["git", "add", "-A"], cwd=self.root)
        run(["git", "commit", "-m", message], cwd=self.root)
        return self.head()

    def push(self) -> None:
        run(["git", "push"], cwd=self.root, capture=False)

    def revert(self, commit: str) -> None:
        run(["git", "revert", "--no-edit", commit], cwd=self.root, capture=False)

    def restore_pre_operation(self, before_head: str, changed_paths: list[str]) -> None:
        run(["git", "reset", "--hard", before_head], cwd=self.root, capture=False)
        for rel in changed_paths:
            path = self.root / rel
            exists_in_head = run(
                ["git", "cat-file", "-e", f"{before_head}:{rel}"],
                cwd=self.root,
                check=False,
            ).returncode == 0
            if not exists_in_head and path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
