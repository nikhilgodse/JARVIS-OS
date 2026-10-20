import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.modules.files import FileManager, exact_entry
from jarvis.skills.files import resolve_delete, _do_delete, _clean_local_query


class TestFilesGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis-ut-")
        with open(os.path.join(self.tmp, "ProbeFile.txt"), "w") as f:
            f.write("x")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_exact_entry(self):
        self.assertEqual(exact_entry(self.tmp, "ProbeFile.txt"), "ProbeFile.txt")
        self.assertEqual(exact_entry(self.tmp, "probefile.txt"), "ProbeFile.txt")
        self.assertIsNone(exact_entry(self.tmp, "missing.txt"))

    def test_case_variant_refused(self):
        path, err = resolve_delete("probefile.txt", self.tmp)
        self.assertIsNone(path)
        self.assertIn("Did you mean", err)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "ProbeFile.txt")))

    def test_exact_resolves(self):
        path, err = resolve_delete("ProbeFile.txt", self.tmp)
        self.assertIsNone(err)
        self.assertTrue(path.endswith("ProbeFile.txt"))

    def test_missing(self):
        path, err = resolve_delete("nope.txt", self.tmp)
        self.assertIsNone(path)
        self.assertIn("Not found", err)

    def test_escape_refused(self):
        path, err = resolve_delete("../outside.txt", self.tmp)
        self.assertIsNone(path)

    def test_do_delete_exact(self):
        target = os.path.join(self.tmp, "Gone.txt")
        with open(target, "w") as f:
            f.write("x")
        msg = _do_delete(target)
        self.assertIn("Deleted", msg)
        self.assertFalse(os.path.exists(target))

    def test_do_delete_case_variant_refused(self):
        msg = _do_delete(os.path.join(self.tmp, "PROBEFILE.TXT"))
        self.assertIn("Refusing", msg)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "ProbeFile.txt")))

    def test_clean_local_query(self):
        self.assertEqual(_clean_local_query("jarvis os file in desktop"), "jarvis os")
        self.assertEqual(_clean_local_query("open the resume folder"), "resume")


if __name__ == "__main__":
    unittest.main()
