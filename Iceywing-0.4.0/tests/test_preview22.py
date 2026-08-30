from __future__ import annotations

import sys
from pathlib import Path

import pytest

import iceywing
from iceywing import environment, popflow
from iceywing.config import ProjectConfig
from iceywing.util import IceywingError, configure_output


ROOT = Path(__file__).resolve().parents[1]


def test_preview22_version_and_installer_postconditions():
    assert iceywing.__version__ == "0.4.0"
    assert 'version = "0.4.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    source = (ROOT / "bootstrap.ps1").read_text(encoding="utf-8")
    assert "$process.WaitForExit()" in source
    assert "$process.Refresh()" in source
    assert "return [PSCustomObject]@{ ExitCode = $exitCode }" in source
    assert "Get-InstalledIceywing" in source
    assert "both module and launcher checks passed" in source
    assert "accepting the verified postcondition" in source
    assert "[OK] Install / upgrade (already current)" in source
    assert '"unknown"' in source


def test_windows_setup_clears_progress_before_completion_lines():
    source = (ROOT / "bootstrap.ps1").read_text(encoding="utf-8")
    check_line = 'Write-Host "[OK] Check Python $version"'
    warning_line = 'Write-Host "[WARN] Normal install failed; retrying for the current user"'
    install_line = 'Write-Host "[OK] Install / upgrade (already current)"'

    for line in (check_line, warning_line, install_line):
        line_at = source.index(line)
        assert source.rfind("Set-SetupProgress -Completed", 0, line_at) != -1


def test_windows_setup_only_suggests_manual_admin_on_permission_denial():
    source = (ROOT / "bootstrap.ps1").read_text(encoding="utf-8")
    assert "Test-PermissionDenied" in source
    assert "right-click Setup.bat" in source
    assert "Run as administrator" in source
    assert "-Verb RunAs" not in source
    assert "--force-reinstall" not in source


def test_neuroscape_verification_failure_shows_tail_exit_code_and_log(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    marker = "NEUROSCAPE_TYPECHECK_FAILED_AT_SEMANTIC_PLANNER"
    failing_command = [
        sys.executable,
        "-c",
        f"print('{marker}'); raise SystemExit(7)",
    ]
    monkeypatch.setattr(
        environment,
        "_task",
        lambda _config, name: failing_command if name == "verify" else None,
    )
    monkeypatch.setenv("ICEYWING_HOME", str(tmp_path / "state"))
    config = ProjectConfig(root=tmp_path, name="NeuroScape2.0-Cirno")

    configure_output()
    with pytest.raises(IceywingError) as captured:
        popflow.verify(config)

    output = capsys.readouterr().out
    message = str(captured.value)
    assert "* Verify · NeuroScape2.0-Cirno" in output
    assert "exit 7" in message
    assert marker in message
    assert "Log:" in message


def test_pop_status_is_read_only_and_never_touches_remote(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    calls: list[str] = []

    class ReadOnlyRepo:
        def branch(self) -> str:
            calls.append("branch")
            return "feat/semantic-planner-v1"

        def clean(self) -> bool:
            calls.append("clean")
            return True

        def __getattr__(self, name: str):
            raise AssertionError(f"pop status attempted unexpected Git operation: {name}")

    monkeypatch.setattr(popflow.GitRepo, "discover", lambda _root: ReadOnlyRepo())
    (tmp_path / "iceywing.toml").write_text("", encoding="utf-8")
    config = ProjectConfig(root=tmp_path, name="NeuroScape2.0-Cirno")

    popflow.status(config)

    output = capsys.readouterr().out
    assert calls == ["branch", "clean"]
    assert "feat/semantic-planner-v1" in output
    assert "Already up to date" not in output
    assert "Switched to a new branch" not in output
