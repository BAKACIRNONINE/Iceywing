from __future__ import annotations

import inspect
import sys
from pathlib import Path

import iceywing

from iceywing.cli import _extract_output_flags, parser
from iceywing.environment import _runtime_summary
from iceywing import popflow
from iceywing.util import configure_output, progress, run_live_logged

ROOT = Path(__file__).resolve().parents[1]


def test_preview13_version():
    assert iceywing.__version__ == "0.4.0a24"
    assert "0.4.0a24" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_top_level_run_accepts_project_path(tmp_path: Path):
    args = parser().parse_args(["run", str(tmp_path)])
    assert args.section == "run"
    assert args.path == tmp_path


def test_verbose_and_quiet_flags_can_be_after_subcommand():
    filtered, verbose, quiet = _extract_output_flags(["run", "C:/demo", "--verbose"])
    assert filtered == ["run", "C:/demo"]
    assert verbose is True
    assert quiet is False


def test_quiet_progress_suppresses_progress(capsys):
    configure_output(quiet=True)
    try:
        progress(1, 2, "[OK]", "Check")
        assert capsys.readouterr().out == ""
    finally:
        configure_output()


def test_runtime_summary_keeps_access_logs_quiet(capsys):
    seen: set[tuple[str, str]] = set()
    assert _runtime_summary('INFO: 127.0.0.1 - "GET /api/sessions HTTP/1.1" 200 OK', seen) is False
    assert capsys.readouterr().out == ""
    assert _runtime_summary("  Local:   http://localhost:5173/", seen) is True
    assert "Frontend" in capsys.readouterr().out


def test_live_runner_can_summarize_lines(tmp_path: Path):
    lines: list[str] = []
    result = run_live_logged(
        [sys.executable, "-c", "print('ready on http://127.0.0.1:9999')"],
        cwd=tmp_path,
        label="demo",
        log_prefix="preview13-test",
        on_line=lines.append,
    )
    assert result.returncode == 0
    assert any("ready on" in line for line in lines)


def test_push_is_explicit_and_has_no_confirmation_prompt():
    source = inspect.getsource(popflow.push)
    assert "confirm_required" not in source
    assert "--dry-run" in source
    assert "run_logged" in source


def test_resume_reuses_verification_checkpoint():
    source = inspect.getsource(popflow.resume)
    assert "Verification checkpoint" in source
    assert "repo.diff_hash() == expected_hash" in source
