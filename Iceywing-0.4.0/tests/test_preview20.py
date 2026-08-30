from __future__ import annotations

import sys
from pathlib import Path

import iceywing

from iceywing import environment, popflow
from iceywing.config import ProjectConfig
from iceywing.util import configure_output


ROOT = Path(__file__).resolve().parents[1]


def test_preview20_version_and_dependencies():
    assert iceywing.__version__ == "0.4.0"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.4.0"' in pyproject
    assert 'dependencies = ["psutil>=7.0"]' in pyproject
    assert "rich" not in pyproject.lower()


def test_windows_setup_uses_native_progress_and_path_check():
    source = (ROOT / "bootstrap.ps1").read_text(encoding="utf-8")
    assert "Write-Progress" in source
    assert "Installing / upgrading Iceywing" in source
    assert "Get-Command iceywing -All" in source
    assert "Other Iceywing commands remain on PATH" in source


def test_pop_verify_hides_successful_neuroscape_output(tmp_path: Path, monkeypatch, capsys):
    noisy_command = [
        sys.executable,
        "-c",
        "print('NEUROSCAPE_TYPESCRIPT_OUTPUT_SHOULD_STAY_IN_LOG')",
    ]
    monkeypatch.setattr(
        environment,
        "_task",
        lambda _config, name: noisy_command if name == "verify" else None,
    )
    monkeypatch.setenv("ICEYWING_HOME", str(tmp_path / "state"))
    config = ProjectConfig(root=tmp_path, name="NeuroScape2.0-Cirno")

    configure_output()
    popflow.verify(config)

    output = capsys.readouterr().out
    assert "NEUROSCAPE_TYPESCRIPT_OUTPUT_SHOULD_STAY_IN_LOG" not in output
    assert "[OK]" in output
    log_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "state" / "logs").glob("*.log")
    )
    assert "NEUROSCAPE_TYPESCRIPT_OUTPUT_SHOULD_STAY_IN_LOG" in log_text


def test_pop_diff_does_not_verify_or_change_project(tmp_path: Path, monkeypatch, capsys):
    class FakeRepo:
        def diff_stat(self) -> str:
            return ""

        def diff_names(self) -> str:
            return ""

    monkeypatch.setattr(popflow.GitRepo, "discover", lambda _root: FakeRepo())

    def unexpected_verify(*_args, **_kwargs):
        raise AssertionError("pop diff must not run project verification")

    monkeypatch.setattr(popflow.environment, "verify", unexpected_verify)
    config = ProjectConfig(root=tmp_path, name="NeuroScape2.0-Cirno")

    popflow.diff(config)

    output = capsys.readouterr().out
    assert output == "* Pop Flow diff\n\nNo working-tree diff.\n"
