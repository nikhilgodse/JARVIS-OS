"""Recurring task automation: `automate <sec> <cmd>`, `jobs`."""

import itertools
import threading

from ..core import speaker
from ..utils import storage

_counter = itertools.count(1)


class Scheduler:
    def __init__(self, router=None):
        self.router = router
        self.jobs = {}
        self._lock = threading.Lock()
        # schedule() has always written jobs to disk, but nothing ever read
        # them back: every recurring task silently vanished on restart and a
        # cancelled one stayed in jobs.json forever. Resume them here instead.
        self._load()

    def bind(self, router):
        self.router = router

    def _ticker(self, command, every, stop):
        while not stop.wait(every):
            try:
                if self.router:
                    self.router.run(command, silent=True)
            except Exception:
                pass

    def _load(self):
        """Resume the tasks schedule() persisted."""
        global _counter
        try:
            saved = storage.load("jobs", {})
        except Exception:
            return
        if not isinstance(saved, dict):
            return
        ids = []
        for raw_id, j in sorted(saved.items(), key=lambda kv: str(kv[0])):
            if not isinstance(j, dict) or not j.get("command"):
                continue
            try:
                # Never trust the file: every=0 would spin stop.wait() hot.
                every = max(1, int(j.get("every")))
                jid = int(raw_id)
            except (TypeError, ValueError):
                continue
            stop = threading.Event()
            t = threading.Thread(target=self._ticker,
                                 args=(j["command"], every, stop), daemon=True)
            with self._lock:
                self.jobs[jid] = {"every": every, "command": j["command"],
                                  "stop": stop, "thread": t}
            ids.append(jid)
            t.start()
        if ids:
            # Otherwise the next scheduled task would reuse a loaded id.
            _counter = itertools.count(max(ids) + 1)

    def _forget(self, jid):
        """Drop the persisted copy so a cancelled task cannot return."""
        try:
            saved = storage.load("jobs", {})
            if isinstance(saved, dict):
                saved.pop(str(jid), None)
                storage.save("jobs", saved)
        except Exception:
            pass

    def schedule(self, every, command):
        try:
            every = max(1, int(every))
        except (TypeError, ValueError):
            speaker.error_msg("Usage: automate <seconds> <command>")
            return
        if not command:
            speaker.error_msg("Usage: automate <seconds> <command>")
            return
        jid = next(_counter)
        stop = threading.Event()
        t = threading.Thread(target=self._ticker,
                             args=(command, every, stop), daemon=True)
        with self._lock:
            self.jobs[jid] = {"every": every, "command": command,
                              "stop": stop, "thread": t}
        t.start()
        try:
            saved = storage.load("jobs", {})
            if not isinstance(saved, dict):
                saved = {}
            saved[str(jid)] = {"every": every, "command": command}
            storage.save("jobs", saved)
        except Exception:
            pass
        speaker.success_msg(f"Task #{jid} scheduled every {every}s: {command}")

    def list(self):
        with self._lock:
            jobs = dict(self.jobs)
        if not jobs:
            speaker.line("No scheduled tasks.")
            return
        speaker.header("SCHEDULED TASKS")
        for jid, j in sorted(jobs.items()):
            speaker.raw(f"  #{jid}  every {j['every']}s  {j['command']}")

    def cancel(self, jid):
        try:
            jid = int(jid)
        except (TypeError, ValueError):
            speaker.error_msg("Usage: jobs cancel <id>")
            return
        with self._lock:
            job = self.jobs.pop(jid, None)
        if not job:
            speaker.error_msg(f"No task #{jid}.")
            return
        job["stop"].set()
        # schedule() wrote it to disk -- take it back out, or it returns on
        # the next restart after the user already cancelled it.
        self._forget(jid)
        speaker.success_msg(f"Task #{jid} cancelled.")

    def clear(self):
        with self._lock:
            jobs = list(self.jobs.values())
            self.jobs.clear()
        for j in jobs:
            j["stop"].set()
