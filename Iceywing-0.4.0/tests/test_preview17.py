from __future__ import annotations

from pathlib import Path

import iceywing

ROOT = Path(__file__).resolve().parents[1]


def test_preview17_version():
    assert iceywing.__version__ == "0.4.0"


def test_selftest_uses_runtime_api_instead_of_recursive_run_cli():
    source = (ROOT / "src" / "iceywing" / "selftest.py").read_text(encoding="utf-8")
    assert "from .runtime import identify, is_alive, terminate_tree" in source
    assert '[sys.executable, "-m", "iceywing", "run"' not in source


def test_selftest_retains_failed_artifacts_by_not_forcing_cleanup():
    source = (ROOT / "src" / "iceywing" / "selftest.py").read_text(encoding="utf-8")
    assert "mkdtemp" in source
    assert "ctx.restore_environment()" in source
    assert "shutil.rmtree" in source
