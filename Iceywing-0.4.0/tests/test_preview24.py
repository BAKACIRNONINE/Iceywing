from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import iceywing
from iceywing import environment, popflow, util
from iceywing.config import ProjectConfig
from iceywing.util import configure_output
from iceywing.verification import VerificationFailed, format_summary, parse_output


ROOT = Path(__file__).resolve().parents[1]


def test_preview24_version_and_release_notes():
    assert iceywing.__version__ == "0.4.0"
    assert 'version = "0.4.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "RELEASE_NOTES_0.4-preview24.md").exists()


def test_neuroscape_vitest_vite_summary_deduplicates_chunk_warning(tmp_path: Path):
    output = """
 RUN  v3.2.7 E:/workspace/study-recorder-server
 ✓ tests/server.test.mjs (7 tests) 56ms
 Test Files  7 passed (7)
      Tests  20 passed (20)

 RUN  v3.2.7 E:/workspace/frontend
 ✓ tests/ui.test.ts (4 tests) 31ms
 Test Files  20 passed (20)
      Tests  67 passed (67)

vite v6.1.0 building for production...
(!) Some chunks are larger than 500 kB after minification.
(!) Some chunks are larger than 500 kB after minification.
✓ built in 3.75s
"""
    result = parse_output(output, passed=True, duration_s=8.9, log_path=tmp_path / "verify.log")

    assert result.test_files == 27
    assert result.tests == 87
    assert result.build_ok is True
    assert result.warnings == 1
    assert format_summary(result) == "✓ Verify  27 files · 87 tests · build OK · 1 warning · 8.9s"


def test_pop_verify_keeps_raw_output_in_log_and_prints_only_summary(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    script = """print(r'''Test Files  3 passed (3)\nTests  9 passed (9)\nNOISY_RAW_DETAIL\n✓ built in 1.25s''')"""
    command = [sys.executable, "-c", script]
    monkeypatch.setattr(environment, "_task", lambda _config, name: command if name == "verify" else None)
    monkeypatch.setenv("ICEYWING_HOME", str(tmp_path / "state"))
    config = ProjectConfig(root=tmp_path, name="NeuroScape2.0-Cirno")

    configure_output()
    popflow.verify(config)

    output = capsys.readouterr().out
    assert "NOISY_RAW_DETAIL" not in output
    assert "[OK] Verify  3 files · 9 tests · build OK" in output

    logs = list((tmp_path / "state" / "logs").glob("*-verify.log"))
    assert len(logs) == 1
    assert "NOISY_RAW_DETAIL" in logs[0].read_text(encoding="utf-8")
    result_json = logs[0].with_suffix(".json")
    assert result_json.exists()
    data = json.loads(result_json.read_text(encoding="utf-8"))
    assert data["tests"] == 9
    assert data["test_files"] == 3


def test_verbose_streams_single_verifier_run_and_still_logs(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    counter = tmp_path / "counter.txt"
    script = (
        "from pathlib import Path; "
        f"p=Path({str(counter)!r}); "
        "n=int(p.read_text())+1 if p.exists() else 1; p.write_text(str(n)); "
        "print('RAW_VERBOSE_OUTPUT'); print('Test Files  1 passed (1)'); print('Tests  2 passed (2)')"
    )
    command = [sys.executable, "-c", script]
    monkeypatch.setattr(environment, "_task", lambda _config, name: command if name == "verify" else None)
    monkeypatch.setenv("ICEYWING_HOME", str(tmp_path / "state"))
    config = ProjectConfig(root=tmp_path, name="demo")

    configure_output(verbose=True)
    popflow.verify(config)

    output = capsys.readouterr().out
    assert "RAW_VERBOSE_OUTPUT" in output
    assert counter.read_text() == "1"
    logs = list((tmp_path / "state" / "logs").glob("*-verify.log"))
    assert len(logs) == 1
    assert "RAW_VERBOSE_OUTPUT" in logs[0].read_text(encoding="utf-8")


def test_failure_is_stage_focused_and_preserves_full_log(
    tmp_path: Path,
    monkeypatch,
):
    lines = [f"noise-{index}" for index in range(40)]
    lines[20] = "src/planner.ts(18,5): error TS2322: Type 'number' is not assignable to type 'string'."
    script = "import sys; print(" + repr("\n".join(lines)) + "); sys.exit(7)"
    command = [sys.executable, "-c", script]
    monkeypatch.setattr(environment, "_task", lambda _config, name: command if name == "verify" else None)
    monkeypatch.setenv("ICEYWING_HOME", str(tmp_path / "state"))
    config = ProjectConfig(root=tmp_path, name="demo")

    configure_output()
    with pytest.raises(VerificationFailed) as captured:
        popflow.verify(config)

    message = str(captured.value)
    assert "Verify · typecheck" in message
    assert "error TS2322" in message
    assert "noise-0" not in message
    assert "noise-39" not in message
    assert "Log:" in message
    assert captured.value.result.log_path.exists()


def test_resume_prints_compact_verify_commit_and_next(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("ICEYWING_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("ICEYWING_PROGRESS", "dynamic")
    util.configure_output()
    events: list[dict[str, object]] = []

    class FakeRepo:
        root = tmp_path

        def clean(self) -> bool:
            return False

        def diff_hash(self) -> str:
            return "verified-diff"

        def commit(self, message: str) -> str:
            assert message == "feat: semantic planner v1"
            return "a1b2c3d4e5f6" * 4

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
    result = parse_output(
        "Test Files  27 passed (27)\nTests  87 passed (87)\n(!) Some chunks are larger than 500 kB\n✓ built in 1.0s",
        passed=True,
        duration_s=8.9,
        log_path=tmp_path / "verify.log",
    )
    monkeypatch.setattr(popflow.environment, "verify", lambda *_args, **_kwargs: result)
    config = ProjectConfig(root=tmp_path, name="NeuroScape2.0-Cirno")

    popflow.resume(config)

    output = capsys.readouterr().out
    assert "* Resume · neuroscape-semantic-planner-v1" in output
    assert "✓ Verify  27 files · 87 tests · build OK · 1 warning · 8.9s" in output
    assert "✓ Commit  a1b2c3d4e5f6" in output
    assert "Next: iceywing pop push" in output
    assert "[OK] Resumed and committed" not in output
