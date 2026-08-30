import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from iceywing.gitops import GitRepo
from iceywing.util import IceywingError, run


class Preview3RegressionTests(unittest.TestCase):
    def test_run_capture_false_failure_does_not_raise_attribute_error(self):
        with self.assertRaises(IceywingError) as ctx:
            run([os.environ.get("PYTHON", "python"), "-c", "raise SystemExit(7)"], capture=False)
        self.assertIn("code 7", str(ctx.exception))

    def test_untracked_file_changes_fingerprint_and_diff(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            (root / "base.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            repo = GitRepo(root)
            clean_hash = repo.diff_hash()
            (root / "new.txt").write_text("new\n", encoding="utf-8")
            self.assertNotEqual(clean_hash, repo.diff_hash())
            self.assertIn("new.txt", repo.diff_stat())
            self.assertIn("??", repo.diff_names())


if __name__ == "__main__":
    unittest.main()
