import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.skills import phrases
from jarvis.skills import opener
from jarvis.skills import pc as pc_skill
from jarvis.skills import timers
from jarvis.skills import notes
from jarvis.skills import _system_skill
from jarvis.modules import pccontrol as pc
from jarvis.utils import storage


class TestPhrases(unittest.TestCase):
    def test_strip_leading_wrapper(self):
        self.assertEqual(phrases.strip_wrap("please play despacito"), "play despacito")
        self.assertEqual(phrases.strip_wrap("can you open notepad"), "open notepad")
        self.assertEqual(phrases.strip_wrap("Hey, play despacito"), "play despacito")
        self.assertEqual(phrases.strip_wrap("hey jarvis volume up"), "jarvis volume up")

    def test_bare_words_untouched(self):
        self.assertEqual(phrases.strip_wrap("hello"), "hello")
        self.assertEqual(phrases.strip_wrap("heyhey play"), "heyhey play")
        self.assertEqual(phrases.strip_wrap("play despacito"), "play despacito")
        self.assertEqual(phrases.strip_wrap("tell me the weather"), "tell me the weather")


class TestVoicePc(unittest.TestCase):
    def test_please_pause_the_music(self):
        with mock.patch.object(pc, "media_action",
                               return_value={"ok": True}) as ma:
            reply = pc_skill.handler("please pause the music", {})
        self.assertEqual(reply, "Media play/pause.")
        ma.assert_called_once_with("play-pause")

    def test_pause_the_music(self):
        with mock.patch.object(pc, "media_action",
                               return_value={"ok": True}):
            self.assertEqual(pc_skill.handler("pause the music", {}),
                             "Media play/pause.")

    def test_please_next_song_skips(self):
        with mock.patch.object(pc, "media_action",
                               return_value={"ok": True}) as ma:
            reply = pc_skill.handler("please next song", {})
        self.assertEqual(reply, "Media next.")
        ma.assert_called_once_with("next")

    def test_read_the_clipboard(self):
        with mock.patch.object(pc, "clipboard_get",
                               return_value={"ok": True, "text": "abc"}):
            self.assertEqual(pc_skill.handler("read the clipboard", {}),
                             "Clipboard: abc")

    def test_type_guard_unaffected_by_wrappers(self):
        # "please type hello" must NOT become keystrokes: the press/type
        # branches keep matching the original text.
        with mock.patch.object(pc, "type_text") as tt:
            reply = pc_skill.handler("please type hello world", {})
        tt.assert_not_called()
        self.assertIsNone(reply)


class TestVoiceTimers(unittest.TestCase):
    def setUp(self):
        self._saved = storage.load("timers", None)

    def tearDown(self):
        for t in list(timers._timers.values()):
            try:
                t["timer"].cancel()
            except Exception:
                pass
        timers._timers.clear()
        storage.save("timers", self._saved if isinstance(self._saved, dict) else {})

    def test_please_set_timer(self):
        reply = timers.handler("please set a timer for 5 minutes", {})
        self.assertIn("Timer set for 5 minute", reply)

    def test_trailing_period(self):
        reply = timers.handler("Set a timer for 5 minutes.", {})
        self.assertIn("Timer set for 5 minute", reply)

    def test_please_cancel_timer(self):
        timers.handler("set a timer for 5 minutes", {})
        reply = timers.handler("please cancel the timer", {})
        self.assertIn("cancelled", reply.lower())


class TestVoiceNotes(unittest.TestCase):
    def setUp(self):
        self._saved = storage.load("notes", None)

    def tearDown(self):
        storage.save("notes", self._saved if isinstance(self._saved, dict) else {})

    def test_please_remember(self):
        reply = notes.handler("please remember my birthday is june first", {})
        self.assertIn("Remembered", reply)
        self.assertIn("birthday", notes.handler("what do you remember", {}))


class TestVoiceSystem(unittest.TestCase):
    def test_how_is_my_system(self):
        reply = _system_skill("how is my system", {})
        self.assertIsNotNone(reply)
        self.assertIn("system", reply.lower())


class TestVoiceOpenTrailingPlease(unittest.TestCase):
    def test_open_notepad_please(self):
        with mock.patch.object(pc, "app_open",
                               return_value={"ok": True}) as ao:
            reply = opener.launch_target("notepad please", {})
        self.assertIsNotNone(reply)
        ao.assert_called_once_with("notepad")

    def test_web_cand(self):
        self.assertEqual(opener._web_cand("the youtube"), "youtube")
        self.assertEqual(opener._web_cand("notepad please"), "notepad")
        self.assertEqual(opener._web_cand("gmail dot com"), "gmail.com")
        self.assertEqual(opener._web_cand("youtube app"), "youtube")


if __name__ == "__main__":
    unittest.main()
