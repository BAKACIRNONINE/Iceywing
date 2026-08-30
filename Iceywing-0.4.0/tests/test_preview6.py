from pathlib import Path

from iceywing.cli import parser
from iceywing.config import ProjectConfig
from iceywing.util import prompt_path


def test_apply_patch_argument_is_optional():
    args = parser().parse_args(["pop", "apply"])
    assert args.patch is None


def test_top_level_up_exists():
    args = parser().parse_args(["up"])
    assert args.section == "up"


def test_baseline_verify_defaults_off(tmp_path: Path):
    config = ProjectConfig(root=tmp_path, name="demo")
    assert config.verify_baseline is False
