import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.modules import scheduler
from jarvis.utils import storage

FAR = 3600  # an hour, so a test ticker never fires on its own


class _StubRouter:
    def __init__(self):
        self.calls = []

    def run(self, command, silent=False):
        self.calls.append((command, silent))


class TestSchedulerPersistence(unittest.TestCase):
    """schedule() always wrote data/jobs.json but _load() was never called."""

    def setUp(self):
        storage.save("jobs", {})
        self._made = []

    def tearDown(self):
        for s in self._made:
            s.clear()          # stop tickers; must NOT touch jobs.json
        storage.save("jobs", {})

    def _make(self):
        s = scheduler.Scheduler(_StubRouter())
        self._made.append(s)
        return s

    def test_resumes_persisted_jobs(self):
        storage.save("jobs", {"1": {"every": FAR, "command": "status"}})
        s = self._make()
        self.assertIn(1, s.jobs)
        self.assertEqual(s.jobs[1]["command"], "status")
        self.assertEqual(s.jobs[1]["every"], FAR)

    def test_empty_store_starts_empty(self):
        s = self._make()
        self.assertEqual(s.jobs, {})

    def test_new_id_skips_loaded_ids(self):
        storage.save("jobs", {"1": {"every": FAR, "command": "status"},
                              "4": {"every": FAR, "command": "battery"}})
        s = self._make()
        self.assertEqual(set(s.jobs), {1, 4})
        s.schedule(FAR, "another")
        # without advancing the counter this reused id 1 and cancel(1) would
        # kill whichever of the two happened to be stored last
        self.assertEqual(set(s.jobs), {1, 4, 5})

    def test_malformed_rows_ignored(self):
        storage.save("jobs", {"x": {"every": 60, "command": "a"},
                              "2": {"every": "soon", "command": "b"},
                              "3": {"every": 60, "command": ""},
                              "4": "not a dict"})
        s = self._make()
        self.assertEqual(s.jobs, {})

    def test_every_is_clamped(self):
        # every=0 would make stop.wait(0) return at once and spin a core
        storage.save("jobs", {"1": {"every": 0, "command": "status"}})
        s = self._make()
        self.assertEqual(s.jobs[1]["every"], 1)

    def test_cancel_removes_from_disk(self):
        storage.save("jobs", {"1": {"every": FAR, "command": "status"}})
        s = self._make()
        s.cancel(1)
        self.assertNotIn(1, s.jobs)
        self.assertEqual(storage.load("jobs", {}), {})

    def test_cancel_unknown_id_leaves_disk_alone(self):
        storage.save("jobs", {"1": {"every": FAR, "command": "status"}})
        s = self._make()
        s.cancel(99)
        self.assertIn("1", storage.load("jobs", {}))

    def test_clear_stops_but_keeps_disk(self):
        # server.py calls sched.clear() in its `finally`. If clear() also
        # wiped the store, every clean shutdown would delete all saved tasks.
        storage.save("jobs", {"1": {"every": FAR, "command": "status"}})
        s = self._make()
        s.clear()
        self.assertEqual(s.jobs, {})
        self.assertIn("1", storage.load("jobs", {}))


if __name__ == "__main__":
    unittest.main()
