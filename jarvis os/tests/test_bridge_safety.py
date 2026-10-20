import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Hermetic storage BEFORE server import: the import registers a master
# password when none exists, which would otherwise touch data/config.json.
from jarvis.utils import storage
storage.DATA_DIR = tempfile.mkdtemp(prefix="jarvis-bridge-test-")

import server


def _post(port, path, body, host="127.0.0.1", origin=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.putrequest("POST", path, skip_host=True)
    conn.putheader("Host", host)
    conn.putheader("Content-Type", "application/json")
    if origin is not None:
        conn.putheader("Origin", origin)
    payload = json.dumps(body).encode("utf-8")
    conn.putheader("Content-Length", str(len(payload)))
    conn.endheaders()
    conn.send(payload)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


def _get(port, path, host="127.0.0.1"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.putrequest("GET", path, skip_host=True)
    conn.putheader("Host", host)
    conn.endheaders()
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


class TestBridgeTrust(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(
            target=cls.srv.serve_forever, kwargs={"poll_interval": 0.05},
            daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.thread.join(timeout=10)
        cls.srv.server_close()

    def test_legit_command_runs(self):
        code, data = _post(self.port, "/api/run", {"command": "hello"})
        self.assertEqual(code, 200)
        self.assertIn("What do you need", data.decode("utf-8"))

    def test_hud_origin_allowed(self):
        code, _ = _post(self.port, "/api/run", {"command": "hello"},
                        origin="http://127.0.0.1:8000")
        self.assertEqual(code, 200)

    def test_spoofed_host_rejected(self):
        code, data = _post(self.port, "/api/run", {"command": "hello"},
                           host="evil.com")
        self.assertEqual(code, 403)
        self.assertIn("forbidden", data.decode("utf-8"))

    def test_foreign_origin_rejected(self):
        code, _ = _post(self.port, "/api/run", {"command": "hello"},
                        origin="http://evil.com")
        self.assertEqual(code, 403)

    def test_transcribe_gated_before_handler(self):
        # Tiny body would be a 400; the trust gate must fire first.
        code, _ = _post(self.port, "/api/transcribe", {}, host="evil.com")
        self.assertEqual(code, 403)

    def test_reads_stay_public(self):
        # Reads are intentionally unauthenticated on loopback; this pins
        # the documented boundary so a future change is deliberate.
        code, _ = _get(self.port, "/api/status", host="evil.com")
        self.assertEqual(code, 200)

    def test_oversize_body_rejected(self):
        # Headers alone declare the violation (Content-Length > limit),
        # so the server 413s without the body ever being sent: no RST race.
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.putrequest("POST", "/api/run", skip_host=True)
        conn.putheader("Host", "127.0.0.1")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(300 * 1024))
        conn.endheaders()
        resp = conn.getresponse()
        self.assertEqual(resp.status, 413)
        conn.close()


if __name__ == "__main__":
    unittest.main()
