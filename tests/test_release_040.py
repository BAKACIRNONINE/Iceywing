from __future__ import annotations

from pathlib import Path
import zipfile

import iceywing
from iceywing import release
from iceywing.cli import parser

ROOT = Path(__file__).resolve().parents[1]


def test_official_version_and_release_notes():
    assert iceywing.__version__ == "0.4.1"
    assert 'version = "0.4.1"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "RELEASE_NOTES_0.4.0.md").exists()


def test_publish_cli_is_the_public_release_command():
    args = parser().parse_args(["release", "publish", "--dry-run"])
    assert args.section == "release"
    assert args.release_cmd == "publish"
    assert args.dry_run is True


def test_stable_release_identity_uses_semver_and_stable_notes(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "iceywing"\nversion = "0.4.0"\n',
        encoding="utf-8",
    )
    notes = tmp_path / "docs" / "RELEASE_NOTES_0.4.0.md"
    notes.parent.mkdir()
    notes.write_text("stable notes", encoding="utf-8")

    identity = release._release_identity(tmp_path)

    assert identity.preview_number is None
    assert identity.tag == "v0.4.0"
    assert identity.title == "Iceywing 0.4.0"
    assert identity.archive_name == "Iceywing-0.4.0.zip"
    assert identity.notes_path == notes


def test_bootstrap_scripts_target_official_version():
    assert 'EXPECTED_VERSION="0.4.0"' in (ROOT / "bootstrap.sh").read_text(encoding="utf-8")
    assert '$ExpectedVersion = "0.4.0"' in (ROOT / "bootstrap.ps1").read_text(encoding="utf-8")


def test_final_zip_contract_can_embed_stable_wheel(tmp_path: Path):
    (tmp_path / "Setup.bat").write_text("setup", encoding="utf-8")
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "iceywing-0.4.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    destination = dist / "Iceywing-0.4.0.zip"

    release._zip_source(tmp_path, destination, installer_wheel=wheel)

    with zipfile.ZipFile(destination) as archive:
        names = set(archive.namelist())
        assert "Iceywing-0.4.0/dist/iceywing-0.4.0-py3-none-any.whl" in names


def test_release_body_starts_with_user_facing_summary(tmp_path: Path):
    notes = tmp_path / "RELEASE_NOTES.md"
    notes.write_text(
        "# Iceywing 0.4.0\n\nReleased on 2026-08-30.\n\nSummary first.\n\n## Highlights\n\n- Fast.\n",
        encoding="utf-8",
    )
    identity = release.ReleaseIdentity(
        project_name="iceywing",
        package_version="0.4.0",
        display_version="0.4.0",
        preview_number=None,
        tag="v0.4.1",
        title="Iceywing 0.4.1",
        archive_name="Iceywing-0.4.1.zip",
        notes_path=notes,
    )

    body = release._release_notes(identity)

    assert body.startswith("Summary first.")
    assert "# Iceywing 0.4.0" not in body
    assert "Released on 2026-08-30." not in body
