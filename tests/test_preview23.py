from __future__ import annotations

import sys
from pathlib import Path

import iceywing
from iceywing import environment, popflow, selftest, util
from iceywing.config import ProjectConfig


ROOT = Path(__file__).resolve().parents[1]


def _force_dynamic_progress(monkeypatch) -> None:
    monkeypatch.setenv("ICEYWING_PROGRESS", "dynamic")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("CLICOLOR", raising=False)
    util.configure_output()


def test_preview23_version_and_no_new_ui_dependency():
    assert iceywing.__version__ == "0.4.1"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.4.1"' in pyproject
    assert 'dependencies = ["psutil>=7.0"]' in pyproject
    assert "rich" not in pyproject.lower()
    assert "tqdm" not in pyproject.lower()


def test_dynamic_progress_uses_color_unicode_and_in_place_updates(
    monkeypatch,
    capsys,
):
    _force_dynamic_progress(monkeypatch)

    util.progress(1, 2, "[....]", "Verify project", live=True)
    util.tick_progress()
    util.progress(1, 2, "[OK]", "Verify project", live=True)
    util.progress(2, 2, "[....]", "Commit change", live=True)
    util.progress(2, 2, "[FAIL]", "Commit change", live=True)

    output = capsys.readouterr().out
    assert "\r" in output
    assert "\x1b[36m" in output
    assert "\x1b[32m" in output
    assert "\x1b[31m" in output
    assert "█" in output
    assert "✓" in output
    assert "✗" in output
    assert any(frame in output for frame in util._SPINNER_FRAMES)
    assert "[######------]" not in output
    assert not util.live_progress_active()


def test_plain_progress_remains_stable_for_redirects(monkeypatch, capsys):
    monkeypatch.setenv("ICEYWING_PROGRESS", "plain")
    util.configure_output()

    util.progress(1, 2, "[....]", "Verify project", live=True)
    util.progress(1, 2, "[OK]", "Verify project", live=True)

    assert capsys.readouterr().out == (
        "[######------] 1/2 [....] Verify project\n"
        "[######------] 1/2 [OK]   Verify project\n"
    )


def test_environment_and_selftest_share_the_dynamic_renderer(monkeypatch, capsys):
    _force_dynamic_progress(monkeypatch)

    environment.progress(1, 1, "[....]", "Setup environment")
    environment.progress(1, 1, "[OK]", "Setup environment")
    selftest.progress(1, 1, "[....]", "CLI")
    selftest.progress(1, 1, "[OK]", "CLI")

    output = capsys.readouterr().out
    assert "Setup environment" in output
    assert "CLI" in output
    assert output.count("✓") == 2
    assert "[############]" not in output
    assert not util.live_progress_active()


def test_pop_resume_animates_verification_and_commits(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    _force_dynamic_progress(monkeypatch)
    monkeypatch.setenv("ICEYWING_HOME", str(tmp_path / "state"))
    events: list[dict[str, object]] = []

    class FakeRepo:
        root = tmp_path

        def clean(self) -> bool:
            return False

        def diff_hash(self) -> str:
            return "verified-diff"

        def commit(self, message: str) -> str:
            assert message == "feat: semantic planner v1"
            return "a" * 40

    history = {
        "operation_id": "6e2a4a86f3",
        "patch_id": "neuroscape-semantic-planner-v1",
        "events": [{"event": "applied"}],
        "verification_required": True,
        "post_diff_hash": "pre-verify-diff",
        "commit_message": "feat: semantic planner v1",
    }
    monkeypatch.setattr(popflow.GitRepo, "discover", lambda _root: FakeRepo())
    monkeypatch.setattr(popflow, "latest", lambda _root: history)
    monkeypatch.setattr(popflow, "append", events.append)
    command = f'"{sys.executable}" -c "import time; time.sleep(0.45)"'
    config = ProjectConfig(
        root=tmp_path,
        name="NeuroScape2.0-Cirno",
        tasks={"verify": command},
    )

    popflow.resume(config)

    output = capsys.readouterr().out
    assert "Verify project" in output
    assert output.count("\r") >= 5
    assert "█" in output
    assert "✓" in output
    assert "[######------]" not in output
    assert "✓ Commit  aaaaaaaaaaaa" in output
    assert "Next: iceywing pop push" in output
    assert {event["event"] for event in events} == {"verified", "committed"}
    assert not util.live_progress_active()
