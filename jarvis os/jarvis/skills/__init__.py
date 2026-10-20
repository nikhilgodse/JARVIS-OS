"""Alexa-style skill dispatcher.

Skills pattern-match the user's words and answer/act directly.
If no skill matches, the LLM chat brain takes over.
"""

import re

from . import websearch as _websearch
from . import wikipedia as _wikipedia
from . import weather as _weather
from . import maths as _maths
from . import timers as _timers
from . import notes as _notes
from . import opener as _opener
from . import pc as _pc
from . import files as _files
from . import whatsapp as _whatsapp


def handle(text: str, ctx: dict):
    """Try each skill in order. Returns skill reply string or None."""
    for skill in SKILL_LIST:
        try:
            reply = skill["handler"](text, ctx)
        except Exception:
            continue
        if reply:
            return f"{skill['name']}: {reply}"
    return None


def list_skills():
    return [(s["name"], s["desc"]) for s in SKILL_LIST]


# --- System summary skill -------------------------------------------------

def _system_skill(text, ctx):
    lower = text.lower()
    asks = ("how much memory", "cpu usage", "how is the system",
            "how is my system", "battery", "disk space", "system status", "ram", "processor usage",
            "how much ram", "how full is", "specification", "specifications", "specs",
            "system info", "my computer specs", "about this computer",
            "status of my laptop", "status of my computer", "status of my pc",
            "my laptop status", "my computer status", "my pc status",
            "laptop specs", "computer specs", "pc specs",
            "how is my laptop", "how is my computer", "how is my pc")
    # Word-boundary match. Plain substring testing let the short ask "ram"
    # fire on any word containing those three letters, so "what is python
    # programming", "grammar check" and "tell me about telegram" all came
    # back with a system report.
    if not any(re.search(r"(?<!\w)" + re.escape(a) + r"(?!\w)", lower) for a in asks):
        return None
    from ..modules import system

    try:
        s = system.get_snapshot()
        parts = [f"Your {s['platform']} system is running at {s['cpu_load']:.0f}% CPU.",
                 f"{system.format_bytes(s['used_mem'])} of {system.format_bytes(s['total_mem'])} memory in use."]
        if s["battery"] and s["battery"].percent is not None:
            parts.append(f"Battery at {int(s['battery'].percent)}% " +
                         ("and charging." if s["battery"].power_plugged else "on battery."))
        if s["disk"]:
            parts.append(f"{system.format_bytes(s['disk'].used)} of {system.format_bytes(s['disk'].total)} disk used.")
        return " ".join(parts)
    except Exception:
        return None


SKILL_LIST = [
    {"name": "whatsapp", "desc": "WhatsApp messaging: send, message, text, tell", "handler": _whatsapp.handler},
    {"name": "files", "desc": "Files & folders: open, find, create, delete", "handler": _files.handler},
    {"name": "opener", "desc": "Open websites, YouTube, and play music", "handler": _opener.handler},
    {"name": "pc", "desc": "Volume, brightness, media, screenshots, clipboard", "handler": _pc.handler},
    {"name": "system", "desc": "Live system status summaries", "handler": _system_skill},
    {"name": "maths", "desc": "Calculations & unit conversion", "handler": _maths.handler},
    {"name": "notes", "desc": "Remember & recall notes", "handler": _notes.handler},
    {"name": "timers", "desc": "Timers & alarms", "handler": _timers.handler},
    {"name": "weather", "desc": "Weather & temperature anywhere", "handler": _weather.handler},
    {"name": "websearch", "desc": "Web search via DuckDuckGo", "handler": _websearch.handler},
    {"name": "wikipedia", "desc": "General knowledge & people lookup", "handler": _wikipedia.handler},
]
