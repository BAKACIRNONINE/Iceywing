from __future__ import annotations

from pathlib import Path

import iceywing

from iceywing.cli import parser
from iceywing.selftest import available_checks

ROOT = Path(__file__).resolve().parents[1]


def test_preview19_version():
    assert iceywing.__version__ == "0.4.0"


def test_cleanup_is_not_a_self_test_stage():
    source = (ROOT / "src" / "iceywing" / "selftest.py").read_text(encoding="utf-8")
    assert 'progress(cleanup_index' not in source
    assert 'Temporary artifacts retained' in source


def test_keep_temp_option_parses():
    args = parser().parse_args(["self-test", "--keep-temp"])
    assert args.keep_temp is True


def test_self_test_checks_stay_capability_focused():
    assert available_checks() == ["cli", "environment", "git", "process"]
