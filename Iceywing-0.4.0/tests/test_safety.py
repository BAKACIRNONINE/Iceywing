import unittest
from iceywing.safety import patch_paths, sensitive_paths


class SafetyTest(unittest.TestCase):
    def test_paths(self):
        text = """diff --git a/a.txt b/a.txt
--- a/a.txt
+++ b/a.txt
@@ -1 +1 @@
-old
+new
diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
"""
        paths = patch_paths(text)
        self.assertEqual(paths, ["a.txt", "package.json"])
        self.assertEqual(sensitive_paths(paths), ["package.json"])


if __name__ == "__main__":
    unittest.main()
