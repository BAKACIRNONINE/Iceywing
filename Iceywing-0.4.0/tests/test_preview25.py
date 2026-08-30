from __future__ import annotations

from pathlib import Path

import iceywing
from iceywing import release
from iceywing.cli import parser
from iceywing.config import ProjectConfig
from iceywing.verification import VerifyResult


ROOT = Path(__file__).resolve().parents[1]


def _write_pyproject(root: Path, version: str = "0.4.0a26") -> None:
    (root / "pyproject.toml").write_text(
        "[project]\nname = \"iceywing\"\nversion = \"" + version + "\"\n",
        encoding="utf-8",
    )


def test_preview25_version_release_notes_and_cli():
    assert iceywing.__version__ == "0.4.0"
    assert 'version = "0.4.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "RELEASE_NOTES_0.4-preview26.md").exists()

    args = parser().parse_args(["release", "preview", "--dry-run"])
    assert args.section == "release"
    assert args.release_cmd == "preview"
    assert args.dry_run is True


def test_release_identity_maps_alpha_version_to_preview(tmp_path: Path):
    _write_pyproject(tmp_path)
    notes = tmp_path / "docs" / "RELEASE_NOTES_0.4-preview26.md"
    notes.parent.mkdir()
    notes.write_text("notes", encoding="utf-8")

    identity = release._release_identity(tmp_path)

    assert identity.tag == "v0.4.0a26"
    assert identity.title == "Iceywing 0.4 Preview26"
    assert identity.archive_name == "Iceywing-0.4-preview26.zip"
    assert identity.notes_path == notes


def test_origin_repo_accepts_https_and_ssh(tmp_path: Path, monkeypatch):
    class Result:
        def __init__(self, stdout: str):
            self.stdout = stdout

    monkeypatch.setattr(release, "run", lambda *_args, **_kwargs: Result("https://github.com/BAKACIRNONINE/Iceywing.git\n"))
    assert release._origin_repo(tmp_path) == "BAKACIRNONINE/Iceywing"

    monkeypatch.setattr(release, "run", lambda *_args, **_kwargs: Result("git@github.com:BAKACIRNONINE/Iceywing.git\n"))
    assert release._origin_repo(tmp_path) == "BAKACIRNONINE/Iceywing"


def test_release_token_prefers_environment_without_persisting(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token-from-env")
    monkeypatch.setenv("GH_TOKEN", "other-token")
    assert release._credential_token() == "token-from-env"


def test_release_dry_run_has_no_git_or_github_writes(tmp_path: Path, monkeypatch, capsys):
    _write_pyproject(tmp_path)

    class FakeRepo:
        root = tmp_path

        def branch(self) -> str:
            return "main"

        def clean(self) -> bool:
            return True

    monkeypatch.setattr(release.GitRepo, "discover", lambda _root: FakeRepo())
    monkeypatch.setattr(release, "_origin_repo", lambda _root: "BAKACIRNONINE/Iceywing")
    monkeypatch.setattr(release, "_github_token_or_error", lambda: (_ for _ in ()).throw(AssertionError("no auth in dry-run")))
    monkeypatch.setattr(release, "_build_artifacts", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no build in dry-run")))
    config = ProjectConfig(root=tmp_path, name="Iceywing")

    release.preview(config, dry_run=True)

    output = capsys.readouterr().out
    assert "* Release · Iceywing 0.4 Preview26" in output
    assert "v0.4.0a26" in output
    assert "dry-run" in output
    assert "Iceywing-0.4-preview26.zip" in output


def test_release_pipeline_orders_verify_build_push_tag_release_upload(tmp_path: Path, monkeypatch, capsys):
    _write_pyproject(tmp_path)
    events: list[str] = []

    class FakeRepo:
        root = tmp_path

        def branch(self) -> str:
            return "main"

        def clean(self) -> bool:
            return True

        def head(self) -> str:
            return "a1b2c3d4e5f67890"

    monkeypatch.setattr(release.GitRepo, "discover", lambda _root: FakeRepo())
    monkeypatch.setattr(release, "_origin_repo", lambda _root: "BAKACIRNONINE/Iceywing")
    monkeypatch.setattr(release, "_ensure_clean", lambda *_args, **_kwargs: "a1b2c3d4e5f67890")

    verify_result = VerifyResult(
        passed=True,
        duration_s=1.2,
        log_path=tmp_path / "verify.log",
        tests=67,
        recognized=True,
    )

    def fake_verify(*_args, **_kwargs):
        events.append("verify")
        return verify_result

    source_zip = tmp_path / "dist" / "Iceywing-0.4-preview26.zip"
    wheel = tmp_path / "dist" / "iceywing-0.4.0a26-py3-none-any.whl"
    source_zip.parent.mkdir()
    source_zip.write_bytes(b"zip")
    wheel.write_bytes(b"wheel")

    def fake_build(*_args, **_kwargs):
        events.append("build")
        return release.ReleaseArtifacts(source_zip=source_zip, wheel=wheel)

    monkeypatch.setattr(release.environment, "verify", fake_verify)
    monkeypatch.setattr(release, "_build_artifacts", fake_build)
    monkeypatch.setattr(release, "_push_head", lambda _repo: events.append("push"))
    monkeypatch.setattr(release, "_ensure_tag", lambda _repo, _tag: events.append("tag"))
    monkeypatch.setattr(release, "_github_token_or_error", lambda: "secret-token")

    def fake_create(*_args, **_kwargs):
        events.append("release")
        return {"id": 25, "html_url": "https://github.com/BAKACIRNONINE/Iceywing/releases/tag/v0.4.0a26"}

    monkeypatch.setattr(release, "_create_or_get_release", fake_create)
    monkeypatch.setattr(release, "_upload_asset", lambda *_args, **_kwargs: events.append("upload"))
    config = ProjectConfig(root=tmp_path, name="Iceywing")

    release.preview(config)

    assert events == ["verify", "build", "push", "tag", "release", "upload"]
    output = capsys.readouterr().out
    assert "67 tests" in output
    assert "Done: v0.4.0a26" in output
