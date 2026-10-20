"""Open websites, YouTube, apps and play music in the browser.

Resolution delegates to pccontrol's web_open (URL > site cache > guess >
search) and to the apps discovery layer for verified application launches.
Supports 'A and B' compound instructions, '<browser> and search X',
'search google/youtube for X', polite request wrappers, and remembers
recent result URLs ('open the first result') plus the last-used browser.
"""

import os
import re
import subprocess
import urllib.parse

from ..modules import pccontrol as pc
from ..modules import apps as _apps
from ..utils import storage
from . import files as _files
from .phrases import strip_wrap

_SHORTCUTS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "maps": "https://maps.google.com",
    "drive": "https://drive.google.com",
    "translate": "https://translate.google.com",
    "calculator": None,
    "notepad": None,
    "paint": None,
    "file manager": None,
    "file explorer": None,
    "explorer": None,
    "my computer": None,
    "this pc": None,
    "my pc": None,
    "files": None,
}

_BROWSERS = {"chrome", "google chrome", "brave", "firefox",
             "edge", "microsoft edge", "opera"}

_BROWSER_LEAD_RE = re.compile(
    r"^(chrome|google chrome|brave|firefox|edge|microsoft edge|opera)"
    r"\s+browser\b\s*(.*)$", re.IGNORECASE)

_PLAY_RE = re.compile(
    r"(?:play|put on|watch)\s+(?:a\s+)?(?:song|music|video)?\s*(.+?)(?:\s+on\s+youtube)?\s*$",
    re.IGNORECASE,
)

# STT often splits it ("on you tube"); normalise before parsing so the
# "on youtube" suffix strips cleanly and replies quote the right words.
_YOUTUBE_SPOKEN_RE = re.compile(r"\byou\s*tube\b", re.IGNORECASE)
# Trailing voice filler ("play despacito please") pollutes the search query
# and the spoken reply. Stripped after the title is captured.
_TRAILING_FILLER_RE = re.compile(r"\s+(?:please|pls)\s*$", re.IGNORECASE)

def _web_cand(seg):
    """Normalised candidate for website/app resolution.

    Voice input adds articles ("open the youtube"), app nouns
    ("open youtube app") and spells out dots ("gmail dot com").
    Only used for shortcut/cache/guess lookups; replies keep the
    user's original words and local-file matching is untouched.
    """
    c = (seg or "").lower()
    c = _YOUTUBE_SPOKEN_RE.sub("youtube", c)
    c = re.sub(r"\s+(?:please|for\s+me)$", "", c).strip()
    c = re.sub(r"^the\s+", "", c).strip()
    c = re.sub(r"\s+(app|application|website|web\s*site|site)$", "", c).strip()
    c = re.sub(r"\s+dot\s+(com|org|net|io|in|co|edu|gov)\b", r".\1", c).strip()
    c = re.sub(r"^www\s+", "www.", c).strip()
    return c.strip()

_NOISE = {"a song", "music", "video", "something", "me something", "a video", "a tune"}

# "play song" / "play video" with no actual title: open YouTube and ask.
_TITLELESS = {"song", "songs", "video", "videos", "tune", "tunes", "something", "anything"}

_YT_SEARCH_RE = re.compile(
    r"^(?:search\s+youtube\s+(?:for\s+)?|youtube\s+search\s+(?:for\s+)?|youtube\s+(?:for\s+)?)(.+)$", re.IGNORECASE)
_GOOGLE_SEARCH_RE = re.compile(
    r"^(?:search\s+google\s+(?:for\s+)?|google\s+(?:for\s+)?)(.+)$", re.IGNORECASE)
_BARE_SEARCH_RE = re.compile(r"^search\s+(?:for\s+)?(.+)$", re.IGNORECASE)
_BARE_SEARCH_SKIP = ("the web", "web for", "internet", "my files", "files",
                     "my computer", "page", "this page", "history")

_RESULT_RE = re.compile(r"^(?:open\s+)?(?:the\s+)?(first|second|third|last)\s+result$",
                        re.IGNORECASE)
_RESULT_IDX = {"first": 0, "second": 1, "third": 2, "last": -1}

_IWANT_RE = re.compile(r"^i\s+want\s+(.+)$", re.IGNORECASE)


def _open_browser(url):
    import webbrowser
    webbrowser.open(url)


def _browser_key(name):
    n = (name or "").lower().strip()
    if n == "google chrome":
        return "chrome"
    if n == "microsoft edge":
        return "edge"
    return n


def _open_in_browser(app, url):
    """Open url in the named browser. Falls back to the default browser.
    Returns True when the named browser was used."""
    exe = None
    try:
        found = _apps.find_app(app or "")
        if found["ok"] and found.get("kind") == "exe":
            exe = found["path"]
    except Exception:
        exe = None
    if exe:
        try:
            subprocess.Popen([exe, url], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                             close_fds=True)
            _set_last_browser(_browser_key(app))
            return True
        except OSError:
            pass
    _open_browser(url)
    return False


def _play(query, browser=None):
    if browser:
        r = pc.youtube_play(query, dry_run=True)
        if r["ok"] and r.get("url"):
            _open_in_browser(browser, r["url"])
            _remember_result(r["url"], browser)
            return f"Playing '{query}' on YouTube in {browser}."
    r = pc.youtube_play(query)
    if r["ok"]:
        _remember_result(r.get("opened") or r.get("url"))
        return f"Playing '{query}' on YouTube."
    return f"Opening YouTube to play '{query}'."


def _play_empty(browser=None):
    url = "https://www.youtube.com"
    if browser:
        _open_in_browser(browser, url)
    else:
        _open_browser(url)
    _remember_result(url, browser)
    return "YouTube is open. Which song should I play?"


def _maybe_play(seg, browser=None):
    """Play-intent resolver. Returns a reply or None (falls through,
    e.g. 'play music' -> media control)."""
    seg = _YOUTUBE_SPOKEN_RE.sub("youtube", seg or "")
    lower = seg.lower()
    if lower.startswith("playing ") and len(lower) > len("playing "):
        # Voice: "start playing X" / bare "playing X".
        seg = "play " + seg[len("playing "):].strip()
        lower = seg.lower()
    m = _PLAY_RE.match(seg)
    if not (m and lower.startswith(("play", "put on", "watch"))
            and not lower.startswith("watch out")):
        return None
    query = m.group(1).strip().strip("?.!")
    query = _TRAILING_FILLER_RE.sub("", query).strip()
    if not query or len(query) <= 1 or query.lower() in _TITLELESS:
        return _play_empty(browser)
    if query.lower() not in _NOISE:
        return _play(query, browser)
    return None


def _google_search_url(q):
    return "https://www.google.com/search?q=" + urllib.parse.quote(q)


def _youtube_search_url(q):
    return ("https://www.youtube.com/results?search_query="
            + urllib.parse.quote(q))


def _do_google_search(q, browser=None):
    url = _google_search_url(q)
    if browser:
        used = _open_in_browser(browser, url)
        where = f" in {browser}" if used else ""
    else:
        _open_browser(url)
        where = ""
    _remember_result(url, browser)
    return f"Searching Google for '{q}'{where}."


def _do_youtube_search(q, browser=None):
    url = _youtube_search_url(q)
    if browser:
        used = _open_in_browser(browser, url)
        where = f" in {browser}" if used else ""
    else:
        _open_browser(url)
        where = ""
    _remember_result(url, browser)
    return f"Searching YouTube for '{q}'{where}."


def _search_intent(seg, browser=None):
    """'search google/youtube for X' and bare 'search X' (browser opens).
    Returns a reply or None. Never steals 'search the web' (text answer)."""
    m = _YT_SEARCH_RE.match(seg)
    if m:
        q = m.group(1).strip().strip("?.!")
        if q:
            return _do_youtube_search(q, browser)
        return None
    m = _GOOGLE_SEARCH_RE.match(seg)
    if m:
        q = m.group(1).strip().strip("?.!")
        if q:
            return _do_google_search(q, browser)
        return None
    m = _BARE_SEARCH_RE.match(seg)
    if m:
        q = m.group(1).strip().strip("?.!")
        if q and not q.lower().startswith(_BARE_SEARCH_SKIP):
            return _do_google_search(q, browser or _get_last_browser())
    return None


def _mem():
    try:
        mem = storage.load("results", None)
        if isinstance(mem, dict):
            return mem
    except Exception:
        pass
    return {"urls": [], "browser": None}


def _remember_result(url, browser=None):
    if not url:
        return
    try:
        mem = _mem()
        urls = [u for u in mem.get("urls", []) if u != url]
        urls.insert(0, url)
        mem["urls"] = urls[:5]
        if browser:
            mem["browser"] = browser
        storage.save("results", mem)
    except Exception:
        pass


def _get_last_browser():
    try:
        return _mem().get("browser")
    except Exception:
        return None


def _set_last_browser(browser):
    if not browser:
        return
    try:
        mem = _mem()
        mem["browser"] = browser
        storage.save("results", mem)
    except Exception:
        pass


def launch_target(target, ctx=None, browser=None):
    """Resolve an 'open/launch' target. Returns a spoken reply or None
    when the target is not something this skill handles (falls back to
    the native app launcher). Supports 'A and B' compound instructions.
    browser= names a browser that web URLs should open in."""
    parts = re.split(r"\s+(?:and|,? then)\s+", (target or "").strip(), flags=re.IGNORECASE)
    replies = []
    cwd = (ctx or {}).get("cwd")
    for seg in parts:
        seg = seg.strip().strip("?.!")
        if not seg:
            continue
        replies.append(_resolve(seg, browser, cwd))
    if not replies:
        return None
    if len(replies) == 1 and replies[0] is None:
        return None
    return re.sub(r"\.\.+", ".", ". ".join(r for r in replies if r))


def _resolve(seg, browser=None, cwd=None):
    lower = seg.lower()

    # "play <song>" part of a compound command
    reply = _maybe_play(seg, browser)
    if reply:
        return reply

    # bare "play" in a compound ("open youtube and play") = resume media
    if lower == "play":
        r = pc.media_action("play-pause")
        return "Media play/pause." if r["ok"] else r["error"]

    # named browser app -> verified launch (never a blind success)
    if lower in _BROWSERS:
        r = _apps.launch_app(lower)
        if r["ok"]:
            _set_last_browser(_browser_key(lower))
            return f"Opening {_browser_key(lower)}."
        return r["error"]

    # Spoken site names ("open the youtube", "open youtube app") resolve
    # before search intents: "youtube app" would otherwise YouTube-search
    # for "app" instead of opening YouTube.
    cand = _web_cand(seg)
    if cand in _SHORTCUTS:
        url = _SHORTCUTS[cand]
        if url is None:
            r = pc.app_open(cand)
            return f"Launching {cand}." if r["ok"] else r["error"]
        if browser:
            _open_in_browser(browser, url)
        else:
            _open_browser(url)
        _remember_result(url, browser)
        return f"Opening {seg}"

    # "search ..." part of a compound command (runs after spoken site
    # names: "youtube app" must open YouTube, not search for "app").
    # Exact shortcut keys never look like a search query, so the
    # shortcut-first order steals nothing here.
    reply = _search_intent(seg, browser)
    if reply:
        return reply

    # known installed app (exact match only, so web words fall through)
    found = _apps.find_app(cand, fuzzy=False)
    if found["ok"]:
        r = _apps.launch_app(cand)
        return f"Opening {seg}." if r["ok"] else r["error"]

    # local file/folder on this laptop before any web fallback
    local = _files.open_local_target(seg, cwd)
    if local:
        return local

    # Everything else resolves via the site cache / guess / search fallback.
    # cand carries the voice normalisation ("the youtube" -> "youtube"),
    # so spoken articles don't push real sites into a Google search.
    if browser:
        r = pc.web_open(cand, dry_run=True)
        if r["ok"] and r.get("url"):
            _open_in_browser(browser, r["url"])
            _remember_result(r["url"], browser)
            return f"Opening {seg}."
        return None
    r = pc.web_open(cand)
    if r["ok"]:
        _remember_result(r.get("opened") or r.get("url"))
        return f"Opening {seg}."
    return None


def _handle_browser_lead(text, ctx):
    m = _BROWSER_LEAD_RE.match(text.strip())
    if not m:
        return None
    app = _browser_key(m.group(1))
    rest = (m.group(2) or "").strip()
    replies = []
    r = _apps.launch_app(app)
    if r["ok"]:
        _set_last_browser(app)
        replies.append(f"Opening {app}.")
    else:
        replies.append(r["error"])
    rest = re.sub(r"^(and|then)\s+", "", rest, flags=re.IGNORECASE).strip()
    if rest:
        sub = launch_target(rest, ctx, browser=app)
        if sub:
            replies.append(sub)
    return re.sub(r"\.\.+", ".", ". ".join(replies))


def handler(text, ctx):
    return _handle((text or "").strip(), ctx, 0)


def _handle(text, ctx, depth):
    lower = text.lower().strip()
    if not lower:
        return None

    # 0) remembered results ("open the first result")
    m = _RESULT_RE.match(lower)
    if m:
        mem = _mem()
        urls = mem.get("urls", [])
        try:
            url = urls[_RESULT_IDX[m.group(1)]]
        except (IndexError, KeyError):
            return "I don't have any recent results. Search for something first."
        _open_in_browser(mem.get("browser"), url)
        return f"Opening the {m.group(1)} result."

    # 1) "<browser> browser [and ...]" ("chrome browser and search X")
    reply = _handle_browser_lead(text, ctx)
    if reply:
        return reply

    # 2) "play X on YouTube" / "play X" ("playing X" is normalised inside).
    # The startswith gate lives in _maybe_play; repeating it here would
    # silently drop its rewrites, so any truthy reply counts.
    reply = _maybe_play(text)
    if reply:
        return reply

    # 3) search intents that open the browser
    reply = _search_intent(text)
    if reply:
        return reply

    # 4) polite request wrappers ("can you open X", "please play Y")
    if depth == 0:
        stripped = strip_wrap(text)
        if stripped and stripped.lower() != lower:
            reply = _handle(stripped, ctx, 1)
            if reply:
                return reply
        m = _IWANT_RE.match(lower)
        if m:
            want = m.group(1).strip()
            want = re.sub(r"\s+(for me|please)$", "", want).strip().strip("?.!")
            # Voice: "i want to open X" / "i want you to play X" /
            # "i want to hear X". The "to" is filler, never content.
            want = re.sub(r"^(?:you\s+)?to\s+", "", want).strip()
            # "hear X" / "listen to X" is a play request ("hear about X"
            # stays informational and falls through to chat/LLM).
            want = re.sub(r"^(?:hear(?!\s+about\b)|listen\s+to)\s+",
                          "play ", want).strip()
            if want:
                if want.startswith(("open ", "launch ", "start ", "bring up ", "play ")):
                    return _handle(want, ctx, 1)
                if (want in _SHORTCUTS or want in _BROWSERS
                        or _apps.find_app(want, fuzzy=False)["ok"]
                        or re.match(r"^[\w-]+(\.[\w-]+)+", want)):
                    return launch_target(want, ctx)

    # 5) "open / launch / start / bring up <app-or-url>"
    if lower.startswith(("open ", "launch ", "start ", "bring up ", "go to ", "browse ")):
        raw = re.sub(r"^(open|launch|start|bring up|go to|browse)\s+", "", text.strip())
        if raw:
            reply = launch_target(raw, ctx)
            if reply:
                return reply

    return None
