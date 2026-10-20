import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server
from http.server import ThreadingHTTPServer


class TestServer(unittest.TestCase):
    def test_snapshot_structure(self):
        snap = server.snapshot_json()
        self.assertIn('hostname', snap)
        self.assertIn('cpu_count', snap)
        self.assertIn('local_ip', snap)
        self.assertIn('mem_pct', snap)
        self.assertIn('uptime', snap)
        self.assertGreaterEqual(snap['cpu_count'], 1)

    def test_run_command_status(self):
        reply = server.run_command('status')
        self.assertIn('SYSTEM STATUS', reply)

    def test_run_command_no_echo(self):
        reply = server.run_command('skills')
        self.assertIn('SKILLS', reply)


class TestServerHttp(unittest.TestCase):
    """Live loopback bridge: no password gate, small bodies only."""

    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.thread.join(timeout=5)
        cls.srv.server_close()

    def _url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def _post(self, path, data):
        req = urllib.request.Request(
            self._url(path), data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, {}

    def test_status_public(self):
        with urllib.request.urlopen(self._url("/api/status"), timeout=30) as r:
            self.assertEqual(r.status, 200)
            body = json.loads(r.read().decode("utf-8"))
        self.assertTrue(body.get("online"))
        self.assertIn("snapshot", body)

    def test_run_open_no_token(self):
        status, body = self._post("/api/run", {"command": "skills"})
        self.assertEqual(status, 200)
        self.assertIn("SKILLS", body.get("reply", ""))
        self.assertNotIn("command", body)

    def test_run_empty(self):
        status, body = self._post("/api/run", {"command": "   "})
        self.assertEqual(status, 200)
        self.assertIn("empty command", body.get("reply", ""))

    def test_logs_public(self):
        with urllib.request.urlopen(self._url("/api/logs?since=0"), timeout=30) as r:
            self.assertEqual(r.status, 200)


if __name__ == '__main__':
    unittest.main()
