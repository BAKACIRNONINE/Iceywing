from __future__ import annotations

from pathlib import Path

import iceywing

from iceywing.cli import parser
from iceywing.config import ProjectConfig
from iceywing.environment import (
    _load_run_state,
    _runtime_summary,
    _save_run_state,
    _clear_run_state,
    stop_project,
)

ROOT = Path(__file__).resolve().parents[1]


def test_preview14_version():
    assert iceywing.__version__ == "0.4.0"
    assert "0.4.0" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_run_replace_flag():
    args = parser().parse_args(["run", "C:/demo", "--replace"])
    assert args.section == "run"
    assert args.replace is True


def test_stop_accepts_project_path():
    args = parser().parse_args(["stop", "C:/demo"])
    assert args.section == "stop"
    assert str(args.path).replace("\\", "/") == "C:/demo"


def test_runtime_summary_collects_services(capsys):
    seen: set[tuple[str, str]] = set()
    services: dict[str, str] = {}
    assert _runtime_summary("NeuroScape study recorder: http://127.0.0.1:8787", seen, services)
    assert services["Recorder"] == "http://127.0.0.1:8787"
    assert "Recorder" in capsys.readouterr().out


def test_runtime_summary_warns_on_port_collision(capsys):
    seen: set[tuple[str, str]] = set()
    _runtime_summary("Error: listen EADDRINUSE: address already in use :::8787", seen)
    assert "port already in use" in capsys.readouterr().out


def test_stale_run_state_is_cleaned(tmp_path: Path, monkeypatch):
    config = ProjectConfig(root=tmp_path, name="demo")
    monkeypatch.setenv("ICEYWING_HOME", str(tmp_path / "state"))
    _save_run_state(config, pid=99999999, services={"Frontend": "http://localhost:5173"})
    assert _load_run_state(config) is not None
    stop_project(config, quiet=True)
    assert _load_run_state(config) is None
    _clear_run_state(config)
