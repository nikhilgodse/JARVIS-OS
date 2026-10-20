import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.skills import confirm
from jarvis.utils import storage


class TestConfirm(unittest.TestCase):
    def setUp(self):
        self._saved = storage.load("pending_confirm", None)

    def tearDown(self):
        storage.save("pending_confirm", self._saved if isinstance(self._saved, dict) else {})

    def test_yes_executes(self):
        confirm.request("shutdown", "Shut down?", {})
        dec = confirm.check("yes", {"shutdown"})
        self.assertIsNotNone(dec)
        self.assertEqual(dec["action"], "shutdown")

    def test_no_cancels(self):
        confirm.request("shutdown", "Shut down?", {})
        dec = confirm.check("no", {"shutdown"})
        self.assertEqual(dec, {"cancelled": True})

    def test_unrelated_skill_untouched(self):
        confirm.request("delete", "Delete?", {"path": "x"})
        self.assertIsNone(confirm.check("yes", {"shutdown"}))
        # still pending for its owner
        dec = confirm.check("yes", {"delete"})
        self.assertIsNotNone(dec)

    def test_expiry(self):
        confirm.request("sleep", "Sleep?", {})
        p = storage.load("pending_confirm", {})
        p["ts"] = time.time() - confirm.TTL - 1
        storage.save("pending_confirm", p)
        self.assertIsNone(confirm.check("yes", {"sleep"}))

    def test_chatter_keeps_pending(self):
        confirm.request("restart", "Restart?", {})
        self.assertIsNone(confirm.check("what time is it", {"restart"}))
        self.assertIsNotNone(confirm.check("yes", {"restart"}))


if __name__ == "__main__":
    unittest.main()
