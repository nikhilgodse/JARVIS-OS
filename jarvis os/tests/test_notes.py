import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.skills import notes


class TestNotes(unittest.TestCase):
    def setUp(self):
        self.fake_db = {}
        self.patch_load = mock.patch('jarvis.utils.storage.load', return_value=self.fake_db)
        self.patch_save = mock.patch('jarvis.utils.storage.save', side_effect=lambda k, v: self.fake_db.update(v))
        self.patch_load.start()
        self.patch_save.start()

    def tearDown(self):
        self.patch_load.stop()
        self.patch_save.stop()

    def test_remember_and_recall(self):
        r = notes.handler('remember that wifi is secret123', {})
        self.assertIn('Remembered', r)
        r2 = notes.handler('what is my wifi', {})
        self.assertIn('secret123', r2)

    def test_list_notes(self):
        self.fake_db['server'] = '192.168.1.1'
        r = notes.handler('what do you remember', {})
        self.assertIn('server', r)

    def test_forget_note(self):
        self.fake_db['temp'] = 'delete_me'
        r = notes.handler('forget temp', {})
        self.assertIn('Forgot', r)
        self.assertNotIn('temp', self.fake_db)


if __name__ == '__main__':
    unittest.main()
