from __future__ import annotations

from pathlib import Path

import iceywing


ROOT = Path(__file__).resolve().parents[1]


def test_preview21_version():
    assert iceywing.__version__ == "0.4.1"
    assert 'version = "0.4.1"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_windows_setup_never_opens_an_elevated_window():
    source = (ROOT / "bootstrap.ps1").read_text(encoding="utf-8")
    assert "-Verb RunAs" not in source
    assert "powershell.exe" not in source
    assert "Elevated" not in source
    assert "No administrator window was opened" in source


def test_windows_setup_retries_current_user_in_same_window():
    source = (ROOT / "bootstrap.ps1").read_text(encoding="utf-8")
    assert "retrying for the current user" in source
    assert "@('--user', $wheel.FullName)" in source
    assert "sysconfig.get_preferred_scheme('user')" in source
    assert "Show-Failure" in source


def test_setup_selects_only_the_matching_preview_wheel():
    source = (ROOT / "bootstrap.ps1").read_text(encoding="utf-8")
    assert '"iceywing-$ExpectedVersion-*.whl"' in source
    assert '"dist\\iceywing-*.whl"' not in source


def test_setup_batch_starts_only_one_powershell_process():
    source = (ROOT / "Setup.bat").read_text(encoding="utf-8").lower()
    assert source.count("powershell") == 1
