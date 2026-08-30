import tempfile
import unittest
from pathlib import Path
from iceywing.config import load_config


class ConfigTest(unittest.TestCase):
    def test_default(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = load_config(Path(td))
            self.assertIn("main", cfg.protected_branches)


if __name__ == "__main__":
    unittest.main()
