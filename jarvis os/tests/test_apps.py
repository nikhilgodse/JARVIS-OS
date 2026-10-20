import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.modules import apps


class TestApps(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(apps.normalize("Google Chrome"), "chrome")
        self.assertEqual(apps.normalize("  the VS Code app "), "code")
        self.assertEqual(apps.normalize("Chrome Browser"), "chrome")

    def test_missing_app_honest(self):
        r = apps.find_app("notepadqq-xyz-missing", fuzzy=False)
        self.assertFalse(r["ok"])
        self.assertIn("couldn't find", r["error"])

    def test_chrome_lookup_honest(self):
        r = apps.find_app("chrome")
        self.assertIn("ok", r)
        if r["ok"]:
            self.assertTrue(os.path.isfile(r["path"]))
        else:
            self.assertIn("couldn't find", r["error"])

    def test_close_protected(self):
        r = apps.close_app("explorer")
        self.assertFalse(r["ok"])
        self.assertIn("protected", r["error"])


if __name__ == "__main__":
    unittest.main()
