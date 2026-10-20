import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.skills import timers


class TestTimers(unittest.TestCase):
    def tearDown(self):
        timers.handler('cancel timer', {})

    def test_set_timer(self):
        r = timers.handler('set a 10 second timer', {})
        self.assertIn('Timer set for 10 second', r)

    def test_list_timers(self):
        timers.handler('set a 15 minute timer', {})
        r = timers.handler('show timers', {})
        self.assertIn('#', r)
        self.assertIn('15 minute', r)

    def test_cancel_timer(self):
        timers.handler('set a 30 second timer', {})
        r = timers.handler('cancel timer', {})
        self.assertIn('cancelled', r)


if __name__ == '__main__':
    unittest.main()
