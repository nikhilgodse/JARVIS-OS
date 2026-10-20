"""Timers and alarms ("set a 5 minute timer", "show timers", "cancel")."""

import re
import threading
import time

from ..utils import storage
from .phrases import strip_wrap

_lock = threading.Lock()
_timers = {}
_counter = [0]
_spoken_cb = None


def set_spoken_cb(cb):
    global _spoken_cb
    _spoken_cb = cb


def _say(msg):
    if _spoken_cb:
        try:
            _spoken_cb(msg)
        except Exception:
            pass


def _persist():
    try:
        storage.save("timers", {str(i): {"label": t["label"], "fires_at": t["fires_at"]}
                                for i, t in _timers.items()})
    except Exception:
        pass


def handler(text, ctx):
    # Voice wraps ("please ...", "hey jarvis ...") and STT leaves trailing
    # punctuation ("... 5 minutes."). Strip the wrapper up front and let the
    # tail tolerate sentence-final punctuation.
    lower = strip_wrap(text).lower().strip()

    # "set a 5 minute timer" / "set a timer for 5 minutes" / "timer for 90 seconds".
    # Only the number-first phrasing used to match, so the far more natural
    # "set a timer for 5 minutes" fell through to the LLM, which just talked
    # about timers instead of setting one.
    tail = r"(?:\s+(?:please|now|right\s+now|from\s+now))?\s*[?.!]*\s*$"
    for pat in (r"^(?:set|start|create|make)\s+(?:a\s+|an\s+)?([\d.]+)\s*(second|minute|hour)s?\s+timer",
                r"^(?:set|start|create|make)\s+(?:a\s+|an\s+)?timer\s+(?:for|of)\s+([\d.]+)\s*(second|minute|hour)s?",
                r"^timer\s+(?:for\s+)?([\d.]+)\s*(second|minute|hour)s?"):
        m = re.match(pat + tail, lower)
        if m:
            break
    if m:
        try:
            amount = float(m.group(1))
        except ValueError:
            return None
        unit = m.group(2)
        secs = amount * {"second": 1, "minute": 60, "hour": 3600}[unit]
        if secs <= 0:
            return None
        with _lock:
            _counter[0] += 1
            tid = _counter[0]
            fires_at = time.time() + secs
            label = f"{amount:g} {unit}"
            timer = threading.Timer(secs, _fire, args=(tid,))
            timer.daemon = True
            _timers[tid] = {"label": label, "fires_at": fires_at, "timer": timer}
            timer.start()
            _persist()
        when = time.strftime("%H:%M:%S", time.localtime(fires_at))
        return (f"Timer set for {label} ({when}). "
                f"{len(_timers)} active timer(s) running.")

    if re.match(r"^(show|list|what are my|how many)\b.*\btimers?\b", lower) or lower in ("timers", "show timers"):
        with _lock:
            items = dict(_timers)
        if not items:
            return "No active timers."
        parts = []
        for tid, t in sorted(items.items()):
            left = max(0, int(t["fires_at"] - time.time()))
            parts.append(f"#{tid}: {t['label']} ({left}s left)")
        return "Timers: " + "; ".join(parts)

    m = re.match(r"^(?:cancel|stop|remove|delete|clear)\s+(?:the\s+|my\s+)?timer(?:\s+#?(\d+))?(?:\s+please)?\s*$", lower)
    if m or lower in ("cancel timer", "stop timer"):
        num = m.group(1) if m else None
        with _lock:
            if num:
                tid = int(num)
                t = _timers.pop(tid, None)
                if t:
                    t["timer"].cancel()
                    _persist()
                    return f"Timer #{tid} cancelled."
                return f"No timer #{tid}."
            if not _timers:
                return "No active timers."
            for t in _timers.values():
                t["timer"].cancel()
            _timers.clear()
            _persist()
            return "All timers cancelled."

    return None


def _fire(tid):
    with _lock:
        t = _timers.pop(tid, None)
        _persist()
    _say(f"Timer done: {t['label']} elapsed." if t else "Timer done.")
