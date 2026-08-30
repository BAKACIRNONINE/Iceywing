from __future__ import annotations

import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .util import IceywingError, sha256_file


@dataclass
class ChangePackage:
    source: Path
    patch: Path
    sha256: str
    package_id: str
    project: str | None = None
    branch: str | None = None
    base_commit: str | None = None
    summary: str | None = None
    commit_message: str | None = None
    delete_after_success: bool | None = None
    tempdir: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self.tempdir:
            self.tempdir.cleanup()
            self.tempdir = None


def load(path: Path) -> ChangePackage:
    path = path.expanduser().resolve()
    if not path.exists():
        raise IceywingError(f"Patch does not exist: {path}")

    digest = sha256_file(path)

    if path.suffix.lower() != ".icepatch":
        return ChangePackage(
            source=path,
            patch=path,
            sha256=digest,
            package_id=path.stem,
        )

    if not zipfile.is_zipfile(path):
        raise IceywingError(".icepatch must be a ZIP archive.")

    td = tempfile.TemporaryDirectory(prefix="iceywing-")
    target = Path(td.name)

    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if not {"manifest.toml", "change.patch"}.issubset(names):
            td.cleanup()
            raise IceywingError(".icepatch requires manifest.toml and change.patch.")
        zf.extract("manifest.toml", target)
        zf.extract("change.patch", target)

    manifest = tomllib.loads((target / "manifest.toml").read_text(encoding="utf-8"))
    project = manifest.get("project", {})
    base = manifest.get("base", {})
    change = manifest.get("change", {})
    cleanup = manifest.get("cleanup", {})

    return ChangePackage(
        source=path,
        patch=target / "change.patch",
        sha256=digest,
        package_id=str(manifest.get("id", path.stem)),
        project=project.get("name"),
        branch=base.get("branch"),
        base_commit=base.get("commit"),
        summary=change.get("summary"),
        commit_message=change.get("commit_message"),
        delete_after_success=cleanup.get("delete_package_after_success"),
        tempdir=td,
    )
