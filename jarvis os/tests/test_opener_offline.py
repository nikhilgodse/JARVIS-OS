import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.skills import files as _files
from jarvis.skills import opener
from jarvis.utils import storage


class TestOpenerOffline(unittest.TestCase):
    def setUp(self):
        self._saved = storage.load("results", None)

    def tearDown(self):
        storage.save("results", self._saved if isinstance(self._saved, dict) else {"urls": [], "browser": None})

    def test_no_local_match_returns_none(self):
        with tempfile.TemporaryDirectory(prefix="jarvis-ut-") as tmp:
            self.assertIsNone(_files.open_local_target("zzqx-no-such-thing", tmp))

    def test_ambiguous_asks_without_opening(self):
        with tempfile.TemporaryDirectory(prefix="jarvis-ut-") as tmp:
            open(os.path.join(tmp, "alpha-report.txt"), "w").close()
            open(os.path.join(tmp, "alpha-notes.txt"), "w").close()
            with mock.patch("os.startfile") as sf:
                reply = _files.open_local_target("alpha", tmp)
            sf.assert_not_called()
            self.assertIn("several matches", reply)

    def test_search_url_formation(self):
        with mock.patch.object(opener, "_open_browser") as ob:
            reply = opener._do_google_search("machine learning")
        ob.assert_called_once()
        url = ob.call_args[0][0]
        self.assertIn("google.com/search", url)
        self.assertIn("machine%20learning", url)
        self.assertIn("machine learning", reply)

    def test_youtube_search_url_formation(self):
        with mock.patch.object(opener, "_open_browser") as ob:
            reply = opener._do_youtube_search("python tutorials")
        url = ob.call_args[0][0]
        self.assertIn("youtube.com/results", url)
        self.assertIn("python%20tutorials", url)
        self.assertIn("python tutorials", reply)

    def test_search_the_web_not_stolen(self):
        self.assertIsNone(opener._search_intent("search the web for cats"))

    def test_first_result_empty_memory(self):
        storage.save("results", {"urls": [], "browser": None})
        reply = opener.handler("open the first result", {})
        self.assertIn("don't have any recent results", reply)


if __name__ == "__main__":
    unittest.main()
