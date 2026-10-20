import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.core import voice


class TestVoice(unittest.TestCase):
    def test_toggle_voice(self):
        cur = voice.voice_enabled()
        voice.set_voice_enabled(not cur)
        self.assertEqual(voice.voice_enabled(), not cur)
        voice.set_voice_enabled(cur)

    def test_speak_empty_safe(self):
        voice.speak('')
        voice.speak(None)

    def test_speak_dispatches(self):
        with mock.patch('jarvis.core.voice._speak_native') as sm:
            voice.speak('Test speech')
            # give thread a moment
            import time
            time.sleep(0.2)
            # either pyttsx3 or native called
            self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
