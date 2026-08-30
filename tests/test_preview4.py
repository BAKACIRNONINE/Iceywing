import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from iceywing.util import confirm_required, run_logged


class Preview4Tests(unittest.TestCase):
    def test_confirm_required_rejects_invalid_then_accepts_yes(self):
        if os.name == "nt":
            # Windows uses one-key input through msvcrt.getwch().
            with patch("msvcrt.getwch", side_effect=["x", "y"]):
                self.assertTrue(confirm_required("Push?"))
        else:
            with patch("builtins.input", side_effect=["", "yes"]):
                self.assertTrue(confirm_required("Push?"))

    def test_confirm_required_accepts_no(self):
        if os.name == "nt":
            with patch("msvcrt.getwch", return_value="n"):
                self.assertFalse(confirm_required("Push?"))
        else:
            with patch("builtins.input", return_value="n"):
                self.assertFalse(confirm_required("Push?"))

    def test_run_logged_reports_log_on_failure(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(Exception) as ctx:
                run_logged(
                    [sys.executable, "-c", "print('debug-line'); raise SystemExit(3)"],
                    cwd=Path(td),
                    label="test step",
                    log_prefix="test",
                )
            message = str(ctx.exception)
            self.assertIn("Failed while: test step", message)
            self.assertIn("debug-line", message)
            self.assertIn("Full log:", message)


class Preview5EncodingTests(unittest.TestCase):
    def test_run_logged_accepts_utf8_output_independent_of_locale(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_logged(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.buffer.write('✓ 中文 — ok'.encode('utf-8'))",
                ],
                cwd=Path(td),
                label="utf8 output",
                log_prefix="utf8",
            )
            self.assertIn("✓ 中文", result.stdout)


if __name__ == "__main__":
    unittest.main()
