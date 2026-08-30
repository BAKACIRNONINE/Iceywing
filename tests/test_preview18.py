from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import iceywing

from iceywing.cli import parser
from iceywing.runtime import identify, is_alive, terminate_tree
from iceywing.selftest import available_checks

ROOT = Path(__file__).resolve().parents[1]


def test_preview18_version_and_psutil_dependency():
    assert iceywing.__version__ == "0.4.0a24"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'psutil>=7.0' in pyproject


def test_self_test_options_parse():
    args = parser().parse_args(["self-test", "--full", "--only", "process", "--json"])
    assert args.full is True
    assert args.only == ["process"]
    assert args.json_output is True


def test_self_test_lists_small_stable_checks():
    assert available_checks() == ["cli", "environment", "git", "process"]


def test_psutil_runtime_terminates_process(tmp_path: Path):
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=tmp_path)
    identity = identify(process.pid)
    assert identity is not None
    assert is_alive(identity.pid, identity.create_time)
    terminate_tree(identity.pid, create_time=identity.create_time, timeout=1)
    process.wait(timeout=3)
    assert not is_alive(identity.pid, identity.create_time)


def test_bootstrap_installs_dependencies_without_force_reinstall():
    text = (ROOT / "bootstrap.ps1").read_text(encoding="utf-8")
    assert "'--upgrade'" in text
    assert "$wheel.FullName" in text
    assert "--no-deps" not in text
    assert "--force-reinstall" not in text
