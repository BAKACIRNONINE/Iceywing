from __future__ import annotations

from pathlib import Path
import zipfile

import iceywing
from iceywing import release


ROOT = Path(__file__).resolve().parents[1]


def test_preview26_version_and_release_notes():
    assert iceywing.__version__ == "0.4.1"
    assert 'version = "0.4.1"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "RELEASE_NOTES_0.4-preview26.md").exists()


def test_release_zip_is_self_contained_for_windows_setup(tmp_path: Path):
    (tmp_path / "Setup.bat").write_text("setup", encoding="utf-8")
    (tmp_path / "bootstrap.ps1").write_text("bootstrap", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "example.py").write_text("print('ok')", encoding="utf-8")
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "iceywing-0.4.0a26-py3-none-any.whl"
    wheel.write_bytes(b"wheel-bytes")
    unrelated = dist / "iceywing-0.4.0a24-py3-none-any.whl"
    unrelated.write_bytes(b"old-wheel")
    destination = dist / "Iceywing-0.4-preview26.zip"

    release._zip_source(tmp_path, destination, installer_wheel=wheel)

    prefix = destination.stem
    with zipfile.ZipFile(destination) as archive:
        names = set(archive.namelist())
        assert f"{prefix}/Setup.bat" in names
        assert f"{prefix}/bootstrap.ps1" in names
        assert f"{prefix}/dist/{wheel.name}" in names
        assert f"{prefix}/dist/{unrelated.name}" not in names
        assert archive.read(f"{prefix}/dist/{wheel.name}") == b"wheel-bytes"


def test_bootstrap_missing_wheel_message_is_not_stale_preview23_copy():
    script = (ROOT / "bootstrap.ps1").read_text(encoding="utf-8")
    assert "Preview23 installer wheel" not in script
    assert "installer wheel for Iceywing $ExpectedVersion" in script
