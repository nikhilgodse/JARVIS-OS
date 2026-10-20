import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.core import parser


class TestParser(unittest.TestCase):
    def test_alias(self):
        p = parser.parse("launch youtube")
        self.assertEqual(p["command"], "open")
        self.assertEqual(p["args"], ["youtube"])
        self.assertFalse(p["implicit"])

    def test_wake_word_stripped(self):
        p = parser.parse("hey jarvis open youtube")
        self.assertEqual(p["command"], "open")
        self.assertEqual(p["raw"], "open youtube")

    def test_wake_word_bare_jarvis(self):
        p = parser.parse("jarvis, volume up")
        self.assertEqual(p["raw"], "volume up")

    def test_wake_word_keeps_greeting(self):
        p = parser.parse("hey jarvis")
        self.assertEqual(p["command"], "chat")

    def test_wake_word_punctuated(self):
        # STT/typed punctuation must not defeat the strip ("Hey, Jarvis.").
        for text, command, raw in [
            ("Hey, Jarvis. Open YouTube.", "open", "Open YouTube."),
            ("Hey. Jarvis. Open YouTube.", "open", "Open YouTube."),
            ("Hey Jarvis, open YouTube", "open", "open YouTube"),
            ("Jarvis: open youtube", "open", "open youtube"),
            ("OK Jarvis, open youtube", "open", "open youtube"),
            ("Hey, Jarvis. Play despacito.", "chat", "Play despacito."),
        ]:
            p = parser.parse(text)
            self.assertEqual(p["command"], command, text)
            self.assertEqual(p["raw"], raw, text)

    def test_wake_word_punctuated_bare(self):
        p = parser.parse("hey, jarvis")
        self.assertEqual(p["command"], "chat")

    def test_plain_chat_untouched(self):
        p = parser.parse("hello world")
        self.assertEqual(p["command"], "chat")
        self.assertEqual(p["raw"], "hello world")
        self.assertTrue(p["implicit"])

    def test_empty(self):
        p = parser.parse("   ")
        self.assertIsNone(p["command"])


if __name__ == "__main__":
    unittest.main()
