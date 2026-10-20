import os
import sys
import unittest
import webbrowser
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.skills import opener
from jarvis.core import parser
from jarvis.modules import chat as chat_mod
from jarvis.modules import pccontrol as pc


FAKE_YT_HTML = '<html><body>{"videoId":"dQw4w9WgXcQ","x":1}</body></html>'


class _FakeResp:
    def __init__(self, html):
        self._html = html.encode()

    def read(self):
        return self._html

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _stub_network(testcase):
    """Deterministic offline world: fake YouTube scrape, no live guessing,
    no real browser tabs. pc.youtube_play calls webbrowser.open directly,
    so that is the seam we record."""
    testcase._patches = [
        mock.patch("urllib.request.urlopen",
                   return_value=_FakeResp(FAKE_YT_HTML)),
        mock.patch.object(pc, "url_reachable", return_value=False),
        mock.patch("webbrowser.open"),
        mock.patch("jarvis.skills.opener._apps.find_app",
                   return_value={"ok": False}),
        mock.patch("jarvis.skills.opener._apps.launch_app",
                   return_value={"ok": False, "error": "no such app"}),
        mock.patch("jarvis.skills.opener._files.open_local_target",
                   return_value=None),
    ]
    for p in testcase._patches:
        p.start()
    testcase.addCleanup(lambda: [p.stop() for p in testcase._patches])
    return webbrowser.open


class TestVoicePlay(unittest.TestCase):
    def setUp(self):
        from jarvis.utils import storage
        self._saved = storage.load("results", None)
        self._browser_open = _stub_network(self)

    def tearDown(self):
        from jarvis.utils import storage
        storage.save("results", self._saved if isinstance(self._saved, dict)
                     else {"urls": [], "browser": None})

    def _played(self, text):
        # Mirror the server entry: the parser strips "hey jarvis" before
        # skills ever see the text.
        cleaned = parser.parse(text)["raw"] or text
        reply = opener.handler(cleaned, {})
        self.assertIsNotNone(reply, f"no skill handled: {text!r}")
        urls = [c[0][0] for c in self._browser_open.call_args_list]
        self._browser_open.reset_mock()
        self.assertTrue(urls, f"nothing opened for: {text!r}")
        for u in urls:
            self.assertIn("youtube.com", u,
                          f"non-YouTube URL for {text!r}: {u}")
            self.assertNotIn("google.com/search", u,
                             f"search fallback for {text!r}: {u}")
        return reply, urls

    def test_bare_play_variants(self):
        for text in ("play despacito",
                     "play despacito on youtube",
                     "put on despacito",
                     "play the song despacito",
                     "play song despacito",
                     "play despacito video",
                     "play despacito song",
                     "play shape of you by ed sheeran",
                     "play some music"):
            reply, urls = self._played(text)
            self.assertTrue(urls[0].startswith(
                "https://www.youtube.com/watch?v="), text)

    def test_polite_wrappers(self):
        for text in ("can you play despacito",
                     "could you play despacito",
                     "would you play despacito",
                     "please play despacito",
                     "hey, play despacito",
                     "hey jarvis play despacito",
                     "hey jarvis, can you play despacito",
                     "jarvis play despacito"):
            self._played(text)

    def test_i_want_forms(self):
        for text in ("i want to play despacito",
                     "i want you to play despacito",
                     "i want to hear despacito",
                     "i want to listen to despacito",
                     "i want to open youtube"):
            self._played(text)

    def test_i_want_hear_about_stays_informational(self):
        # "hear about X" is a knowledge question, not a play request.
        self.assertIsNone(opener.handler(
            "i want to hear about quantum physics", {}))

    def test_playing_verb(self):
        reply, urls = self._played("playing despacito")
        self.assertIn("watch?v=", urls[0])
        reply, urls = self._played("start playing despacito")
        self.assertIn("watch?v=", urls[0])

    def test_trailing_please_stripped(self):
        reply, _ = self._played("play despacito please")
        self.assertIn("despacito", reply)
        self.assertNotIn("please", reply.lower())

    def test_you_tube_split(self):
        reply, urls = self._played("play despacito on you tube")
        self.assertIn("Playing 'despacito' on YouTube.", reply)

    def test_open_youtube_spoken_forms(self):
        for text in ("open youtube", "open you tube", "open the youtube",
                     "hey jarvis open youtube", "open youtube app"):
            reply, urls = self._played(text)
            self.assertEqual(urls[0], "https://www.youtube.com", text)

    def test_compound_never_opens_wrong_site(self):
        cleaned = parser.parse("open youtube and play despacito")["raw"]
        reply = opener.handler(cleaned, {})
        self.assertIsNotNone(reply)
        urls = [c[0][0] for c in self._browser_open.call_args_list]
        self.assertTrue(urls)
        for u in urls:
            self.assertNotIn("openyoutube.com", u)

    def test_guards_preserved(self):
        # media-control passthrough, "watch out", bare titles unchanged
        self.assertIsNone(opener.handler("play music", {}))
        self.assertIsNone(opener.handler("watch out for traffic", {}))
        reply = opener.handler("play song", {})
        self.assertIn("Which song", reply)

    def test_site_cache_youtube_entry(self):
        sites = pc.load_sites()
        self.assertEqual(sites.get("open youtube"),
                         "https://www.youtube.com")


class TestVoiceGreeting(unittest.TestCase):
    def setUp(self):
        self.brain = chat_mod.ChatBrain()

    def test_greeting_then_command_bails_to_skills(self):
        self.assertEqual(self.brain._local("hey play despacito", {}), "")
        self.assertEqual(self.brain._local("hello open youtube", {}), "")
        self.assertEqual(
            self.brain._local("good morning play despacito", {}), "")

    def test_bare_greetings_unchanged(self):
        greet = self.brain._local("hey", {})
        self.assertTrue(greet)
        self.assertEqual(self.brain._local("hey how are you", {}), greet)
        self.assertEqual(self.brain._local("hello", {}), greet)


if __name__ == "__main__":
    unittest.main()
