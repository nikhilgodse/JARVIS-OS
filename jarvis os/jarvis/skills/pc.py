"""PC control through natural language: volume, brightness, media keys,
browser/YouTube actions, screenshots, clipboard, notifications, IP, key
presses, typing, mouse, mic and speaker tests, power, and closing apps."""

import re

from ..modules import pccontrol as pc
from ..modules import apps as _apps
from . import confirm
from .phrases import strip_wrap

_CLOSE_APP_RE = re.compile(r"(?:close|quit|kill)\s+(?:the\s+)?(?:app\s+|application\s+)?(.+)", re.I)
_NUM_RE = re.compile(r"(?:to|at|of|set)?\s*(\d{1,3})")

# "type"/"write" must only ever dictation-type plain text. Keystroke injection
# is a one-way door: it lands in whatever window happens to have focus. Without
# this guard, "write an email about the meeting" typed 40 characters into the
# user's active app and "type safety in python" did the same, instead of
# reaching the LLM. Erring towards the LLM is always the safe answer, so this
# blocks questions, requests to compose, and topic-shaped leftovers.
_TYPE_BLOCK_RE = re.compile(
    r"\?"
    r"|\b(?:please|about|for me|help me|could you|can you|would you|will you|"
    r"write me|type me|compose|draft|generate|create|make me|give me|tell me|"
    r"explain|describe|summar(?:y|ise|ize)|come up with|instead of)\b"
    r"|\b(?:it down|that down|this down|back to|to me|down for)\b"
    # article + optional filler + a composition noun ("a short story")
    r"|\b(?:an?|the|my|your|another|some|one|this|that)\s+(?:[\w-]+\s+){0,2}"
    r"(?:email|e-?mail|essay|poem|story|song|lyrics|summary|overview|report|"
    r"article|blog|post|reply|response|message|note|notes|letter|paragraph|"
    r"sentence|list|plan|outline|code|function|program(?:me)?|script|class|"
    r"method|tweet|caption|bio|application|composition|query|algorithm|snippet|"
    r"recipe|proposal|spec|documentation|readme|pitch|documentation)\b"
    # a concept in its domain ("type safety in python")
    r"|\b(?:in|for|with|on|of)\s+(?:python|javascript|typescript|java|rust|"
    r"golang|sql|c\+\+|programming|software|coding)\b"
    r"|\b(?:code|function|program|script|class|method|poem|essay|email|story|"
    r"summary|report|article|reply|message|letter|sentence|list|plan|outline|"
    r"draft)\s+(?:in|for|with|on|about|of|that|which|who|to)\b",
    re.I,
)
_BROWSER_WORDS = {
    "new-tab": ("new tab", "open a tab"), "close-tab": ("close tab",),
    "reopen-tab": ("reopen tab", "restore tab", "reopen closed"),
    "next-tab": ("next tab", "switch to next"),
    "prev-tab": ("previous tab", "prev tab", "switch to previous"),
    "new-window": ("new window",),
    "refresh": ("refresh", "reload"),
    "hard-refresh": ("hard refresh", "hard reload"),
    "back": ("go back", "back a page", "browser back"),
    "forward": ("go forward", "forward a page"),
    "address-bar": ("address bar", "open the url bar"),
    "find": ("find on page", "search page", "find in page"),
    "zoom-in": ("zoom in",), "zoom-out": ("zoom out",),
    "zoom-reset": ("zoom reset", "reset zoom", "reset the zoom"),
    "fullscreen": ("fullscreen", "go fullscreen"),
}

_YT_WORDS = {
    "play-pause": ("playpause", "resume video"), "mute": ("mute youtube", "mute video"),
    "fullscreen": ("fullscreen video",),
    "back-10": ("back 10", "rewind 10", "back ten"), "fwd-10": ("forward 10", "fwd 10", "fast forward 10"),
    "back-5": ("back 5", "rewind 5"), "fwd-5": ("forward 5",),
    "speed-up": ("speed up", "faster video", "increase speed"), "speed-down": ("slow down video", "decrease speed"),
    "next-video": ("next video",), "prev-video": ("previous video", "prev video"),
    "captions": ("captions", "subtitles"), "theater": ("theater mode",),
}


def _match_any(lower, words):
    return any(w in lower for w in words)


def _first(lower, items):
    for label, words in items.items():
        if _match_any(lower, words):
            return label
    return None


def _pick_kv(lower, words):
    return _first(lower, words)


def handler(text, ctx):
    lower = text.lower().strip()
    stripped = lower.strip("?.")

    # ---- pending destructive confirmations (this skill's actions only) -----
    dec = confirm.check(text, {"shutdown", "restart", "sleep"})
    if dec is not None:
        if dec.get("cancelled"):
            return "Cancelled."
        return _run_confirmed(dec)

    # ---- system power (before close/restart-app: "restart computer" is power)
    if re.search(r"\block\b", lower):
        r = pc.lock_workstation()
        return "Computer locked." if r["ok"] else r["error"]
    if _match_any(lower, ("cancel shutdown", "abort shutdown", "stop shutdown",
                          "cancel restart", "abort restart")):
        import subprocess
        code = subprocess.run(["shutdown", "/a"], capture_output=True).returncode
        return "Scheduled shutdown cancelled." if code == 0 else "No shutdown was scheduled."
    if _match_any(lower, ("shut down", "shutdown", "power off", "turn off the computer",
                          "turn off my pc", "switch off the computer")):
        return confirm.request("shutdown",
                               "This will shut down the computer in 10 seconds.", {})
    if (stripped in ("restart", "reboot") or _match_any(lower, ("restart the computer",
            "restart my pc", "restart the pc", "restart windows", "restart the system",
            "reboot the computer", "reboot the system"))):
        return confirm.request("restart",
                               "This will restart the computer in 10 seconds.", {})
    if stripped in ("sleep", "go to sleep", "sleep now") or (
            "sleep" in lower and _match_any(lower, ("computer", "pc", "system", "put it to",
                                                    "put the computer", "go to"))):
        return confirm.request("sleep", "This will put the computer to sleep.", {})

    # ---- battery -----------------------------------------------------------
    if _match_any(lower, ("battery", "how much battery")):
        r = pc.battery()
        if not r["ok"]:
            return None
        msg = f"Battery at {r['percent']}%, " + ("charging." if r.get("power_plugged") else "on battery.")
        if r.get("time_remaining"):
            msg += f" {r['time_remaining']} remaining."
        return msg

    # ---- volume -------------------------------------------------------------
    if "volume" in lower or "mute" in lower or "unmute" in lower or _match_any(lower, ("louder", "quieter")):
        return _volume(lower)

    # ---- screenshot (before brightness: "screen" is a substring) ------------
    if _match_any(lower, ("screenshot", "capture screen", "capture the screen", "take a screen", "screen grab")):
        r = pc.screenshot()
        return f"Screenshot saved: {r['path']}" if r["ok"] else "Couldn't take a screenshot."

    # ---- brightness -----------------------------------------------------------
    if "brightness" in lower or ("screen" in lower and _match_any(lower, ("bright", "dim", "dark"))):
        return _brightness(lower)

    # ---- mic / speaker tests ---------------------------------------------------
    if _match_any(lower, ("mic test", "test my mic", "test your mic", "test the mic", "microphone test")):
        r = pc.mic_test(seconds=3)
        if not r["ok"]:
            return r["error"]
        return (f"Mic test: peak {r['peak']}, {r['clipping_pct']}% clipping, "
                f"SNR {r['snr_db']} dB. Verdict: {r['verdict']}.")
    if _match_any(lower, ("speaker test", "test my speakers", "test the speakers", "speaker-test")):
        r = pc.speaker_test(measure=False, duration=0.3)
        played = sum(1 for t in r["tones"] if t["played"])
        return f"Speaker test: {'OK' if played == len(r['tones']) else 'FAILED'} ({played}/{len(r['tones'])} tones played). {r['verdict']}"

    # ---- browser actions -------------------------------------------------------
    action = _first(lower, _BROWSER_WORDS)
    if action and (_match_any(lower, ("tab", "window", "refresh", "reload", "back", "forward", "zoom", "fullscreen", "address", "find on", "search page"))):
        r = pc.browser_action(action)
        return f"Browser {action}." if r["ok"] else r["error"]

    # ---- yt actions -----------------------------------------------------------
    yt = _first(lower, _YT_WORDS)
    if yt:
        r = pc.yt_action(yt)
        return f"YouTube {yt}." if r["ok"] else r["error"]

    # ---- media keys (bare words only, so "play X on youtube" passes on) ------
    # Voice adds wrappers and articles ("please pause the music"): strip
    # those for matching only. The press/type branches below deliberately
    # keep using the original text (keystroke-injection surface).
    media = {"play music", "pause music", "resume music", "stop music",
             "play", "pause", "resume", "next track", "next song", "skip track",
             "skip song", "previous track", "previous song", "prev track", "prev song",
             "next", "previous", "skip", "playing", "whats playing", "what is playing", "now playing"}
    mline = strip_wrap(re.sub(r"\bthe\s+", "", stripped))
    if mline in media or _match_any(mline, ("media play", "media pause", "play next", "go next",
                                            "playing", "whats playing", "what is playing", "now playing")):
        if mline in ("playing", "whats playing", "what is playing", "now playing"):
            r = pc.media_action("status")
            return r.get("note") or "Media playing."
        if mline in ("next", "next track", "next song", "skip", "skip track", "skip song"):
            r = pc.media_action("next")
            return "Media next." if r["ok"] else r["error"]
        if mline in ("previous track", "previous song", "prev track", "prev song", "previous", "prev"):
            r = pc.media_action("prev")
            return "Media previous." if r["ok"] else r["error"]
        r = pc.media_action("play-pause")
        return "Media play/pause." if r["ok"] else r["error"]

    # ---- mouse ---------------------------------------------------------------
    if _match_any(lower, ("double click", "double-click")):
        r = pc.mouse_action("double-click")
        return "Double-clicked." if r["ok"] else r["error"]
    if _match_any(lower, ("right click", "right-click")):
        r = pc.mouse_action("right-click")
        return "Right-clicked." if r["ok"] else r["error"]
    if stripped in ("click", "left click", "mouse click") or re.match(r"^click\b", lower):
        r = pc.mouse_action("click")
        return "Clicked." if r["ok"] else r["error"]
    if "scroll" in lower:
        if _match_any(lower, ("up", "higher")):
            r = pc.mouse_action("scroll", amount=3)
        elif _match_any(lower, ("down", "lower")):
            r = pc.mouse_action("scroll", amount=-3)
        else:
            m = re.search(r"(-?\d+)", lower)
            r = pc.mouse_action("scroll", amount=int(m.group(1))) if m else pc.mouse_action("scroll")
        return "Scrolled." if r["ok"] else r["error"]
    m = re.match(r"move\s+(?:the\s+)?mouse\s+to\s+(-?\d+)[\s,]+(-?\d+)", lower)
    if m:
        r = pc.mouse_action("move", x=int(m.group(1)), y=int(m.group(2)))
        return f"Mouse moved to {m.group(1)}, {m.group(2)}." if r["ok"] else r["error"]

    # ---- clipboard ------------------------------------------------------------
    if "clipboard" in lower or "paste" in lower:
        return _clipboard(lower, text)

    # ---- notifications ---------------------------------------------------------
    if _match_any(lower, ("notify me", "notify", "alert me", "alert", "pop up")):
        m = re.sub(r"^(notify me|notify|alert me|alert|pop up)\s*(?:that\s+|to\s+)?", "", lower)
        m = m.strip().strip("?.!")
        if m:
            pc.notify(m)
            return f"Notification sent: '{m}'."

    # ---- IP --------------------------------------------------------------------
    if _match_any(lower, ("ip address", "my ip", "whats my ip", "ip ")):
        r = pc.ip_info()
        return f"Your IP address is {r.get('local') or 'unknown'}."

    # ---- keys / type -------------------------------------------------------------
    m = re.match(r"(?:press|hit|tap)\s+(.+)", lower)
    if m:
        combo = m.group(1).strip().strip("?.!")
        combo = combo.replace("ctrl+", "ctrl+").replace("windows", "win")
        r = pc.send_keys(combo)
        if r["ok"]:
            return f"Pressed {combo}."
        # "hit me up" / "press the button" are sentences, not chords -- the
        # parse failed because there is no such key. Hand them to the LLM
        # instead of answering with a parser error.
        if len(combo.split()) > 1 and "unknown key" in str(r["error"]):
            return None
        return r["error"]
    m = re.match(r"(?:type|write)\s+(?:out\s+)?(.+)", lower)
    if (m and not _match_any(lower, ("folder", "file"))
            and not _TYPE_BLOCK_RE.search(m.group(1))):
        content = m.group(1).strip().strip("?.")
        r = pc.type_text(content)
        return f"Typed {r.get('typed_chars', '?')} characters into the active window." if r["ok"] else r["error"]

    # ---- close / restart apps (verified, honest) ------------------------------
    # (timers/alarms belong to the timers skill - never steal those words)
    m = re.match(r"(?:restart|reopen)\s+(?:the\s+)?(.+)", lower)
    if m and lower.startswith(("restart", "reopen")):
        app = m.group(1).strip().strip("?.!")
        if "timer" in app or "alarm" in app:
            return None
        if app and app not in ("computer", "pc", "windows", "system", "machine",
                               "jarvis", "chat", "it"):
            r = _apps.restart_app(app)
            return f"{app} restarted." if r["ok"] else r["error"]
    m = _CLOSE_APP_RE.match(lower)
    if m and lower.startswith(("close", "quit", "kill")):
        app = m.group(1).strip().strip("?.!")
        if "timer" in app or "alarm" in app:
            return None
        if app and app not in ("the", "chat", "it"):
            r = _apps.close_app(app)
            if r["ok"]:
                return f"Closed {app}." if r.get("was_running") else f"{app} wasn't running."
            return r["error"]

    return None


def _run_confirmed(dec):
    action = dec.get("action")
    if action == "shutdown":
        r = pc.shutdown_pc(10)
        return ("Shutting down in 10 seconds. Say 'cancel shutdown' to stop it."
                if r["ok"] else r["error"])
    if action == "restart":
        r = pc.restart_pc(10)
        return ("Restarting in 10 seconds. Say 'cancel shutdown' to stop it."
                if r["ok"] else r["error"])
    if action == "sleep":
        r = pc.sleep_pc()
        return "Going to sleep." if r["ok"] else r["error"]
    return None


def _extract_num(lower):
    m = _NUM_RE.search(lower)
    return int(m.group(1)) if m else None


def _volume(lower):
    if "mute" in lower and "unmute" not in lower:
        pc.volume_mute(True)
        return "Muted."
    if "unmute" in lower:
        pc.volume_mute(False)
        return "Unmuted."
    if _match_any(lower, ("up", "increase", "louder", "raise")):
        r = pc.volume_step(_extract_num(lower) or 10)
        return f"Volume up: {r.get('volume')}%" if r["ok"] else r["error"]
    if _match_any(lower, ("down", "decrease", "quieter", "lower")):
        r = pc.volume_step(-(_extract_num(lower) or 10))
        return f"Volume down: {r.get('volume')}%" if r["ok"] else r["error"]
    n = _extract_num(lower)
    if n is not None and _match_any(lower, ("set", "to", "at", "make it")):
        r = pc.volume_set(n)
        return f"Volume set to {r.get('volume')}%" if r["ok"] else r["error"]
    r = pc.volume_get()
    return f"Volume is {r.get('volume')}%" if r["ok"] else r["error"]


def _brightness(lower):
    if _match_any(lower, ("up", "increase", "brighter")):
        r = pc.brightness_get()
        r2 = pc.brightness_set(min(100, (r.get("brightness") or 50) + 10))
        return f"Brightness up: {r2.get('brightness')}%." if r2["ok"] else (r2["error"] if not r["ok"] else "Brightness not adjustable.")
    if _match_any(lower, ("down", "decrease", "dimmer", "lower")):
        r = pc.brightness_get()
        r2 = pc.brightness_set(max(0, (r.get("brightness") or 50) - 10))
        return f"Brightness down: {r2.get('brightness')}%." if r2["ok"] else "Brightness not adjustable."
    n = _extract_num(lower)
    if n is not None:
        r = pc.brightness_set(n)
        return f"Brightness set to {r.get('brightness')}%." if r["ok"] else "This screen doesn't support brightness control."
    r = pc.brightness_get()
    return f"Brightness is {r.get('brightness')}%." if r["ok"] else "Brightness unavailable."


def _clipboard(lower, text):
    m = re.search(r"(?:copy|put|save)\s+(.+?)\s+(?:to|on|onto)\s+(?:the\s+)?clipboard", lower)
    if m:
        content = m.group(1).strip().strip("?.!\"")
        pc.clipboard_set(content)
        return f"Copied '{content}' to the clipboard."
    if _match_any(lower, ("read clipboard", "read the clipboard", "show clipboard",
                           "show the clipboard", "whats on", "paste", "whats in")) or lower.strip("?.") in ("clipboard", "paste"):
        r = pc.clipboard_get()
        return f"Clipboard: {r.get('text') or '(empty)'}" if r["ok"] else r["error"]
    return None
