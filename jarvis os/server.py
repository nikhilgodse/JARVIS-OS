"""JARVIS web bridge - Session 2.

READ-ONLY reference to Session-1 (never edits jarvis/):
    jarvis.main.Router / parser / system / auth / llm / voice / scheduler

Run:
    python server.py            # serves HUD + API on http://127.0.0.1:8000
    python server.py --port 8080

API (same origin, so frontend uses API_BASE = ""):
    GET  /api/status     -> core online, snapshot summary, auth/llm state
    GET  /api/telemetry  -> live cpu/ram for HUD bars
    GET  /api/logs       -> background output (timers, scheduled tasks)
    POST /api/run        -> {"command": "status"} -> {"reply": "..."}
    POST /api/login      -> {"password": "..."}   -> {"ok": true/false}
    POST /api/transcribe -> raw WAV bytes -> {"text": "..."}
Frontend static files are served from ./frontend/.
Stdlib only. No password gate: this bridge only listens on 127.0.0.1.
"""

import collections
import contextlib
import datetime
import io
import json
import os
import re
import sys
import threading
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

from jarvis.core import auth, parser, speaker  # noqa: E402  (read-only use)
from jarvis.main import Router  # noqa: E402
from jarvis.modules import llm, pccontrol, scheduler, system  # noqa: E402
from jarvis.core import voice  # noqa: E402
from jarvis.utils import storage  # noqa: E402

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# ---------------------------------------------------------------- live log
# Scheduler ticks and timer alarms print from background threads, bypassing
# run_command()'s stdout capture. Tee everything into a ring buffer so the
# HUD feed can stream them via GET /api/logs. (Foreground command output
# goes to run_command()'s StringIO instead, so nothing is duplicated.)

LOG_BUF = collections.deque(maxlen=300)
LOG_LOCK = threading.Lock()
LOG_SEQ = [0]
_REAL_STDOUT = sys.stdout


class _TeeWriter:
    def __init__(self, real):
        self.real = real

    def write(self, s):
        try:
            self.real.write(s)
        except Exception:
            pass
        if s:
            text = ANSI_RE.sub("", s)
            if text.strip():
                with LOG_LOCK:
                    for line in text.splitlines():
                        line = line.strip()
                        if line:
                            LOG_SEQ[0] += 1
                            LOG_BUF.append({
                                "i": LOG_SEQ[0],
                                "t": datetime.datetime.now().strftime("%H:%M:%S"),
                                "text": line[:500],
                            })
        return len(s) if s else 0

    def flush(self):
        try:
            self.real.flush()
        except Exception:
            pass


sys.stdout = _TeeWriter(_REAL_STDOUT)

# ---------------------------------------------------------------- router

class WebRouter(Router):
    """Session-1 Router adapted for HTTP: no blocking input(), no os.system,
    no sys.exit, no server-side TTS. All output is captured via stdout."""

    def _login(self, password=""):
        # `login <password>` works from the HUD. Bare `login` tries default.
        pw = (password or "").strip() or auth.DEFAULT_PASSWORD
        if not auth.is_configured():
            auth.register(os.environ.get("JARVIS_MASTER_PASSWORD") or auth.DEFAULT_PASSWORD)
        if auth.authenticate(pw):
            speaker.success_msg("Access granted. Welcome, sir.")
        else:
            speaker.error_msg("Access denied.")

    def _chat_loop(self):
        speaker.line('Chat mode is terminal-only. Send "chat <message>" instead.')

    def _voice_loop(self):
        speaker.line('Voice capture runs in the browser mic. Use "voice on/off" for spoken replies.')

    def _say(self, text):
        # Play audio on server speakers; frontend also does TTS via speechSynthesis.
        speaker.say(text)
        if voice.voice_enabled():
            try:
                voice.speak(text)
            except Exception as e:
                speaker.error_msg(f"TTS error: {e}")

    def run(self, text, silent=False):
        # Intercept web-safe variants before delegating to Session-1 logic.
        parsed = parser.parse(text or "")
        command, args = parsed["command"], parsed["args"]
        implicit = parsed.get("implicit", False)
        if command is None:
            return
        if command == "authenticate":
            return self._login(" ".join(args))
        if command == "clear":
            speaker.line("Terminal feed cleared (server state kept).")
            return
        if command == "shutdown":
            speaker.say("Goodbye, sir. (Server keeps running for the HUD.)")
            return
        if command == "speak":
            # Echo text so HUD can vocalise it; also play on server speakers.
            if not args:
                speaker.error_msg("Usage: speak <text>")
            else:
                text_to_speak = " ".join(args)
                speaker.say(text_to_speak)
                if voice.voice_enabled():
                    voice.speak(text_to_speak)
            return
        if command == "voice" and not args:
            speaker.line('Usage: voice on | voice off  (mic capture runs in the browser)')
            return
        if command == "chat":
            # Session-1 enters an interactive input() loop when args are empty
            # (also for single-word implicit chat). That would hang HTTP, so:
            # - implicit unknown text -> answer it directly via chat brain
            # - explicit bare "chat" -> usage hint instead of blocking loop
            raw = (parsed.get("raw") or "")
            if implicit:
                # "play <song>" is a media command, not chit-chat: resolve it
                # through the same opener skill as the terminal so the exact
                # video opens (not a search page).
                if raw.lower().startswith("play ") and len(raw) > 5:
                    try:
                        from jarvis import skills
                        reply = skills.opener.launch_target(raw)
                    except Exception:
                        reply = None
                    if reply:
                        return speaker.say(reply)
                try:
                    return self._chat_respond(raw)
                except Exception as e:
                    return speaker.error_msg(str(e))
            if not args:
                return self._chat_loop()
        # Everything else (including "open") goes through the exact Session-1
        # pipeline: opener skill (web/YouTube resolution) then launcher.
        try:
            super().run(text, silent=silent)
        except SystemExit:
            speaker.say("Goodbye, sir. (Server keeps running for the HUD.)")


router = WebRouter()
sched = scheduler.Scheduler(router)
router.bind_scheduler(sched)
if not auth.is_configured():
    auth.register(os.environ.get("JARVIS_MASTER_PASSWORD") or auth.DEFAULT_PASSWORD)

_lock = threading.Lock()

# No password gate on this bridge, but POST is not open either: the socket
# only listens on 127.0.0.1 AND state-changing endpoints reject
# non-loopback Host/Origin (DNS-rebinding / cross-origin defense, see
# _bridge_trusted). Oversize bodies are still rejected (413).
# /api/status, /api/telemetry and static files are public reads.
_RUN_BODY_LIMIT = 256 * 1024


def run_command(cmd):
    """Run one Session-1 command, capture printed output, return clean text."""
    buf = io.StringIO()
    with _lock, contextlib.redirect_stdout(buf):
        try:
            router.run(cmd or "")
        except Exception as e:  # Router already guards, belt-and-braces
            speaker.error_msg(str(e))
    return ANSI_RE.sub("", buf.getvalue()).strip() or "(no output)"


def snapshot_json():
    snap = system.get_snapshot()
    total = snap.get("total_mem") or 0
    used = snap.get("used_mem") or 0
    disk = snap.get("disk")
    batt = snap.get("battery")
    try:
        batt_pct = int(batt.percent) if batt and batt.percent is not None else None
        batt_plugged = bool(batt.power_plugged) if batt and batt.power_plugged is not None else None
    except Exception:
        batt_pct, batt_plugged = None, None
    try:
        cfg = storage.load("config", {}) if hasattr(storage, "load") else {}
        home_loc = cfg.get("location") or None
    except Exception:
        home_loc = None
    try:
        ip_data = pccontrol.ip_info()
        local_ip = ip_data.get("local") or "127.0.0.1"
    except Exception:
        local_ip = "127.0.0.1"
    return {
        "hostname": snap.get("hostname"),
        "platform": snap.get("platform"),
        "arch": snap.get("arch"),
        "cpu_count": snap.get("cpu_count"),
        "cpu_model": snap.get("cpu_model"),
        "cpu_load": round(float(snap.get("cpu_load") or 0), 1),
        "mem_used": used,
        "mem_total": total,
        "mem_pct": round(used / total * 100, 1) if total else 0,
        "disk_used": disk.used if disk else 0,
        "disk_total": disk.total if disk else 0,
        "disk_pct": round(disk.used / disk.total * 100, 1) if disk and disk.total else 0,
        "battery_pct": batt_pct,
        "battery_plugged": batt_plugged,
        "uptime": system.format_uptime(snap.get("uptime") or 0),
        "location": home_loc,
        "local_ip": local_ip,
    }

# ---------------------------------------------------------------- HTTP

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=FRONTEND_DIR, **kw)

    def end_headers(self):
        # Always revalidate the HUD assets. Without this the browser keeps a
        # memory-cached app.js (served in <0.1ms, no revalidation), so frontend
        # fixes silently never reach the page.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *a):
        pass  # keep server console clean; scheduler noise stays minimal

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self, limit=_RUN_BODY_LIMIT):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n > limit:
            return None
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            return {}

    def _raw_body(self, limit=8 * 1024 * 1024):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > limit:
            return b""
        return self.rfile.read(n)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/status":
            snap = snapshot_json()
            return self._json({
                "online": True,
                "snapshot": snap,
                "authenticated": auth.is_authenticated(),
                "locked": not auth.is_authenticated(),
                "llm": {"configured": llm.is_configured(), **({"model": llm.settings()["model"]} if llm.is_configured() else {})},
                "voice_enabled": voice.voice_enabled(),
                "providers": llm.provider_info(),
            })
        if path == "/api/providers":
            return self._json(llm.provider_info())
        if path == "/api/telemetry":
            return self._json(snapshot_json())
        if path == "/api/weather":
            qs = urllib.parse.urlparse(self.path).query
            city = urllib.parse.parse_qs(qs).get("city", [None])[0]
            if not city:
                cfg = storage.load("config", {}) if hasattr(storage, "load") else {}
                city = cfg.get("location") or None
            if not city:
                return self._json({"city": None, "weather": None, "note": "No city set. Use: location <city>."})
            ctx = {"location": city}
            try:
                from jarvis.skills import weather as _weather
                w_str = _weather.handler(f"weather in {city}", ctx)
                return self._json({"city": city, "weather": w_str})
            except Exception as e:
                return self._json({"city": city, "weather": None, "error": str(e)})
        if path == "/api/logs":
            qs = urllib.parse.urlparse(self.path).query
            try:
                since = int(urllib.parse.parse_qs(qs).get("since", ["0"])[0])
            except (ValueError, TypeError):
                since = 0
            with LOG_LOCK:
                items = [e for e in LOG_BUF if e["i"] > since][-50:]
                cur = LOG_SEQ[0]
            return self._json({"logs": items, "cursor": cur})
        if path in ("/api/run", "/api/login", "/api/status"):
            return self._json({"error": "use POST"}, 405)
        # static: / -> index.html
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def _bridge_trusted(self):
        """Loopback-only gate for state-changing endpoints.

        The 127.0.0.1 bind alone does not stop a rebinding/cross-origin
        page (the browser will happily POST to 127.0.0.1). Browsers send
        Host always and Origin on POST, so: reject a non-loopback Host,
        and reject a present-but-foreign Origin. Headerless clients
        (curl, local scripts, the terminal never uses HTTP) keep working.
        """
        host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
        if host and host not in ("127.0.0.1", "localhost", "::1", "[::1]"):
            return False
        origin = (self.headers.get("Origin") or "").strip()
        if origin:
            try:
                ohost = (urllib.parse.urlparse(origin).hostname or "").lower()
            except Exception:
                return False
            if ohost not in ("127.0.0.1", "localhost", "::1"):
                return False
        return True

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not self._bridge_trusted():
            return self._json({"error": "forbidden: bridge accepts loopback Host/Origin only"}, 403)
        if path == "/api/run":
            data = self._body()
            if data is None:
                return self._json({"error": "request too large"}, 413)
            cmd = str(data.get("command") or "")
            if not cmd.strip():
                return self._json({"reply": "(empty command)"})
            reply = run_command(cmd)
            # the submitted command is never echoed back (it may contain a
            # password or API key)
            return self._json({"reply": reply})
        if path == "/api/login":
            data = self._body()
            if data is None:
                return self._json({"error": "request too large"}, 413)
            pw = str(data.get("password") or "")
            reply = run_command(f"login {pw}".strip())
            return self._json({"ok": auth.is_authenticated(), "reply": reply})
        if path == "/api/transcribe":
            # Body = raw WAV bytes; uses Session-1's SpeechRecognition if installed.
            audio = self._raw_body()
            if len(audio) < 1000:
                return self._json({"error": "empty audio - hold the mic and speak"}, 400)
            try:
                import speech_recognition as sr
            except ImportError:
                return self._json({"error": "server STT not installed (pip install SpeechRecognition pyaudio)"}, 501)
            import tempfile
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio)
                    tmp = f.name
                r = sr.Recognizer()
                with sr.AudioFile(tmp) as src:
                    data = r.record(src)
                try:
                    text = r.recognize_google(data)
                except sr.UnknownValueError:
                    return self._json({"error": "could not understand the audio"}, 422)
                except sr.RequestError as e:
                    return self._json({"error": f"speech service error: {e} (internet required)"}, 502)
                return self._json({"text": text})
            except Exception as e:
                return self._json({"error": f"transcribe failed: {e}"}, 500)
            finally:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass
        return self._json({"error": "unknown endpoint"}, 404)


def main():
    port = 8000
    for i, a in enumerate(sys.argv):
        if a == "--port" and i + 1 < len(sys.argv):
            try:
                port = int(sys.argv[i + 1])
            except ValueError:
                pass
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"JARVIS bridge online: http://127.0.0.1:{port}  (HUD + /api/*)")
    print("Session-1 jarvis/ used read-only; nothing modified.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBridge stopped.")
    finally:
        try:
            sched.clear()
        except Exception:
            pass


if __name__ == "__main__":
    main()
