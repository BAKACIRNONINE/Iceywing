from __future__ import annotations

import os
from pathlib import Path

import iceywing

from iceywing.cli import parser
from iceywing.util import state_home

ROOT = Path(__file__).resolve().parents[1]


def test_preview15_version():
    assert iceywing.__version__ == "0.4.0a24"
    assert "0.4.0a24" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_self_test_command_parses_without_project():
    args = parser().parse_args(["self-test"])
    assert args.section == "self-test"


def test_state_home_can_be_isolated(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ICEYWING_HOME", str(tmp_path))
    assert state_home() == tmp_path


def test_selftest_source_uses_finite_isolated_checks():
    source = (ROOT / "src" / "iceywing" / "selftest.py").read_text(encoding="utf-8")
    assert '"up"' in source
    assert '"pop", "push"' in source
    assert 'terminate_tree' in source
    assert 'mkdtemp' in source
    assert '[sys.executable, "-m", "iceywing", "run"' not in source


def test_selftest_does_not_depend_on_windows_console_groups():
    source = (ROOT / "src" / "iceywing" / "selftest.py").read_text(encoding="utf-8")
    assert "CREATE_NEW_PROCESS_GROUP" not in source
    assert "taskkill" not in source
    assert "stdin=subprocess.DEVNULL" in source
