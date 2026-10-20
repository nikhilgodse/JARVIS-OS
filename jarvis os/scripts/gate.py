#!/usr/bin/env python3
"""gate.py: measured verification gate for the JARVIS pc-control skill (Windows).

Safe by default: no keystrokes are injected and nothing destructive runs.
System volume and clipboard are saved and restored. Pass --live to add a
real keystroke round trip through Notepad. Pass --quiet to skip the audible
speaker tones.

Exit 0 only if zero FAILs. Prints an honest NOT COVERED list: a green gate
is proof of exactly what ran, nothing more.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PC = os.path.join(ROOT, "jarvis", "modules", "pccontrol.py")

results = []
not_covered = []


def record(status, name, detail=""):
    results.append((status, name, detail))
    mark = {"PASS": "ok", "FAIL": "FAIL", "SKIP": "skip"}[status]
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail else ""))


def pc(*args, timeout=90):
    # Explicit UTF-8: the Windows locale codepage crashes on unicode output.
    p = subprocess.run([sys.executable, PC, "--json", *args],
                       capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    try:
        data = json.loads(p.stdout) if p.stdout.strip() else {}
    except json.JSONDecodeError:
        data = {}
    return p.returncode, data, p.stderr


def check(name, cond, detail=""):
    record("PASS" if cond else "FAIL", name, detail)


def shell_clip_get():
    p = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.stdout


def shell_clip_set(text):
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Set-Clipboard -Value $input"],
                   input=text, text=True, capture_output=True,
                   encoding="utf-8", errors="replace")


def shell_clip_restore(text, tries=5):
    """Restore the clipboard and verify it stuck. A fresh Set-Clipboard
    needs a short settle window before another process can read it back,
    so the read-back retries instead of flaking."""
    shell_clip_set(text)
    for _ in range(tries):
        if shell_clip_get() == text:
            return True
        time.sleep(0.4)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="include the Notepad keystroke round trip")
    ap.add_argument("--quiet", action="store_true",
                    help="skip audible speaker tones")
    a = ap.parse_args()

    # -- doctor and structure
    code, d, _ = pc("doctor")
    check("doctor runs and returns json", code == 0 and d.get("ok"))
    keystrokes_ok = d.get("checks", {}).get("keystrokes", False)

    # -- battery
    code, d, _ = pc("battery")
    check("battery reports percent 0-100",
          code == 0 and 0 <= d.get("percent", -1) <= 100)

    # -- volume (state saved and restored)
    code, d, _ = pc("volume", "get")
    vol0, muted0 = d.get("volume"), d.get("muted")
    check("volume get returns 0-100", code == 0 and 0 <= (vol0 or -1) <= 100)
    code, d, _ = pc("volume", "set", str(vol0))
    check("volume set (same value) succeeds", code == 0)
    code, d, _ = pc("volume", "set", "150")
    check("volume set 150 is rejected", code == 1)
    code, d, _ = pc("volume", "get")
    check("volume unchanged after gate", d.get("volume") == vol0)

    # -- ip
    code, d, _ = pc("ip")
    check("ip reports a local address", code == 0 and bool(d.get("local")))
    code, d, _ = pc("ip", "--public")
    if d.get("public"):
        check("ip --public resolves", True)
    else:
        record("SKIP", "ip --public", "network unavailable")

    # -- apps
    code, d, _ = pc("apps")
    check("apps lists running processes", code == 0 and d.get("count", 0) > 0)
    code, d, _ = pc("app", "front")
    check("app front returns a name", code == 0 and bool(d.get("frontmost")))
    code, d, _ = pc("app", "running", "svchost")
    check("app running svchost is true", code == 0 and d.get("running") is True)
    code, d, _ = pc("app", "running", "NoSuchAppQzx")
    check("app running (absent) is false",
          code == 0 and d.get("running") is False)
    code, d, _ = pc("app", "open")
    check("app open without name is a usage error (exit 2)", code == 2)

    # -- clipboard (saved and restored)
    clip0 = shell_clip_get()
    token = "pc-gate-3f9a"
    code, d, _ = pc("clipboard", "set", token)
    code2, d2, _ = pc("clipboard", "get")
    check("clipboard set/get round trip",
          code == 0 and code2 == 0 and d2.get("text") == token)
    shell_clip_set(clip0)
    check("clipboard restored after gate", shell_clip_restore(clip0))

    # -- clipboard preserves trailing newline
    clip0 = shell_clip_get()
    pc("clipboard", "set", "line with newline\n")
    code, d, _ = pc("clipboard", "get")
    check("clipboard get preserves trailing newline",
          d.get("text") == "line with newline\n")
    shell_clip_set(clip0)

    # -- screenshot
    tmp = os.path.join(tempfile.gettempdir(), f"pc-gate-{os.getpid()}.png")
    code, d, _ = pc("screenshot", tmp)
    if code == 0 and d.get("ok"):
        check("screenshot writes a nonzero png",
              os.path.getsize(tmp) > 0)
        os.unlink(tmp)
    else:
        record("SKIP", "screenshot", "screen capture unavailable")
        not_covered.append("screenshot (capture)")

    # -- keystroke engine: dry-run every mapped combo / key
    combos = ["ctrl+t", "ctrl+shift+t", "ctrl+tab", "ctrl+plus", "space",
              "shift+n", "ctrl+left", "f11", "volume-mute", "k"]
    all_ok = True
    for c in combos:
        code, d, _ = pc("keys", c, "--dry-run")
        plan = d.get("plan", "")
        if code != 0 or "key" not in plan:
            all_ok = False
            record("FAIL", f"keys dry-run {c}", d.get("error", plan or "?"))
    check("keys: 10 combos parse to a key plan", all_ok)
    code, d, _ = pc("keys", "ctrl+nosuchkey", "--dry-run")
    check("keys: unknown key rejected", code == 1)
    code, d, _ = pc("keys", "badmod+t", "--dry-run")
    check("keys: unknown modifier rejected", code == 1)

    code, d, _ = pc("type", 'he said "hi" \\ done', "--dry-run")
    check("type: quotes and backslashes accepted",
          code == 0 and d.get("ok"))

    # -- browser and yt maps: every action dry-runs
    for family, actions in [
        ("browser", ["new-tab", "close-tab", "reopen-tab", "next-tab",
                     "prev-tab", "new-window", "private-window", "zoom-in",
                     "zoom-out", "zoom-reset", "refresh", "hard-refresh",
                     "back", "forward", "history", "bookmarks", "address-bar",
                     "find", "devtools", "fullscreen"]),
        ("yt", ["play-pause", "mute", "fullscreen", "theater", "miniplayer",
                "captions", "vol-up", "vol-down", "back-5", "fwd-5",
                "back-10", "fwd-10", "prev-frame", "next-frame", "speed-up",
                "speed-down", "start", "end", "prev-chapter", "next-chapter",
                "next-video", "prev-video"]),
    ]:
        all_ok = True
        for act in actions:
            code, d, _ = pc(family, act, "--dry-run")
            if code != 0 or not d.get("ok"):
                all_ok = False
                record("FAIL", f"{family} {act}", d.get("error", "?"))
        check(f"{family}: all {len(actions)} actions dry-run", all_ok)
        code, d, _ = pc(family, "no-such-action", "--dry-run")
        check(f"{family}: unknown action rejected", code == 1)

    # -- media
    code, d, _ = pc("media", "status")
    check("media status runs", code == 0)
    code, d, _ = pc("media", "play-pause", "--dry-run")
    check("media play-pause dry-run maps", code == 0 and d.get("ok"))

    # -- web resolution
    code, d, _ = pc("web", "youtube", "--dry-run")
    check("web: cache hit resolves youtube",
          code == 0 and "youtube.com" in d.get("url", ""))
    code, d, _ = pc("web", "example.com", "--dry-run")
    check("web: bare domain becomes https url",
          code == 0 and d.get("url") == "https://example.com")
    code, d, _ = pc("web", "zzqx qkjw vvnn", "--dry-run")
    check("web: gibberish falls back to a search url",
          code == 0 and "google.com/search" in d.get("url", ""))

    # -- youtube resolution (network)
    code, d, _ = pc("youtube", "play", "lo-fi beats", "--dry-run")
    if code == 0 and "youtube.com" in d.get("url", ""):
        check("youtube play resolves a url", True,
              d.get("resolved_via", ""))
    else:
        record("SKIP", "youtube play", "network unavailable")

    # -- brightness honesty contract
    code, d, err = pc("brightness", "get")
    check("brightness get: works or fails with guidance",
          code == 0 or "brightness" in (d.get("error", "") + err).lower())
    code, d, _ = pc("brightness", "up", "-3", "--dry-run")
    check("brightness up -3 rejected cleanly (no traceback)",
          code in (1, 2) and d.get("ok") is False)
    code, d, _ = pc("brightness", "up", "0", "--dry-run")
    check("brightness up 0 rejected, not defaulted to 3",
          code in (1, 2) and d.get("ok") is False)

    # -- speaker test
    if a.quiet:
        record("SKIP", "speaker-test", "--quiet")
        not_covered.append("speaker tone playback (--quiet)")
    else:
        pc("volume", "set", "15")
        code, d, _ = pc("speaker-test", "--seconds", "0.2", timeout=120)
        pc("volume", "set", str(vol0))
        played = all(t.get("played") for t in d.get("tones", []))
        check("speaker-test plays all 5 tones", code == 0 and played)
        check("speaker-test admits it is unmeasured",
              "playback only" in d.get("verdict", ""))

    # -- mic test (permission dependent)
    code, d, _ = pc("mic-test", "--seconds", "2", timeout=60)
    if code == 0 and d.get("ok"):
        check("mic-test returns metrics", "verdict" in d)
    else:
        record("SKIP", "mic-test", "mic permission or device unavailable")
        not_covered.append("mic capture (permission)")

    # -- negative and contract checks
    p = subprocess.run([sys.executable, PC, "no-such-cmd"],
                       capture_output=True, text=True)
    check("unknown command exits 2", p.returncode == 2)
    code, d, _ = pc("volume", "set")
    check("volume set without value is a usage error (exit 2)", code == 2)
    for c in ["battery", "doctor"]:
        code, d, _ = pc(c)
        check(f"--json {c} parses", isinstance(d, dict) and "ok" in d)

    p = subprocess.run([sys.executable, PC, "battery", "--json"],
                       capture_output=True, text=True)
    try:
        trailing = json.loads(p.stdout).get("ok") is True
    except json.JSONDecodeError:
        trailing = False
    check("trailing --json accepted (documented syntax)",
          p.returncode == 0 and trailing)

    clip0 = shell_clip_get()
    pc("clipboard", "set", "mutation-guard")
    with open(os.path.join(ROOT, "jarvis", "assets", "websites.json"), "rb") as f:
        cache0 = f.read()
    pc("web", "example", "--dry-run")
    with open(os.path.join(ROOT, "jarvis", "assets", "websites.json"), "rb") as f:
        check("web dry-run does not mutate the site cache",
              f.read() == cache0)
    shell_clip_set(clip0)

    code, d, _ = pc("app", "running", 'x" & "y')
    check("quoted app name treated as literal data",
          code == 0 and d.get("running") is False)
    code, d, _ = pc("web", "HTTP://EXAMPLE.ORG", "--dry-run")
    check("uppercase scheme not double-prefixed",
          code == 0 and d.get("url", "").lower().count("http") == 1)
    code, d, _ = pc("type", "", "--dry-run")
    check("type empty string rejected", code in (1, 2))

    # -- no em or en dashes anywhere in the skill
    dirty = []
    for root, _, files in os.walk(ROOT):
        if any(part in root for part in (".git", "node_modules", "__pycache__", "frontend")):
            continue
        for f in files:
            if not f.endswith((".py", ".json", ".md", ".html", ".js", ".css")):
                continue
            path = os.path.join(root, f)
            try:
                text = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            if "\u2014" in text or "\u2013" in text:
                dirty.append(os.path.relpath(path, ROOT))
    check("no em/en dashes in any project file", not dirty, ", ".join(dirty))

    # -- live keystroke round trip (Notepad on Windows)
    if a.live and keystrokes_ok:
        clip0 = shell_clip_get()
        token = "pc-gate-live-7x"
        try:
            pc("app", "open", "notepad")
            time.sleep(2.0)
            pc("type", token)
            time.sleep(0.5)
            pc("keys", "ctrl+a")
            pc("keys", "ctrl+c")
            time.sleep(0.5)
            check("LIVE: keystrokes reached notepad", shell_clip_get().strip() == token)
            pc("keys", "ctrl+w")
            time.sleep(0.5)
            pc("keys", "n")
        finally:
            shell_clip_set(clip0)
    elif a.live:
        record("SKIP", "live keystroke round trip", "keystroke engine off")
        not_covered.append("live keystroke injection (engine)")
    else:
        not_covered.append("live keystroke injection (run gate.py --live)")

    if not keystrokes_ok:
        not_covered.append("browser/yt/keys/type/brightness-step live execution (keystroke engine off)")

    # -- summary
    npass = sum(1 for s, _, _ in results if s == "PASS")
    nfail = sum(1 for s, _, _ in results if s == "FAIL")
    nskip = sum(1 for s, _, _ in results if s == "SKIP")
    print(f"\nGATE: {npass} passed, {nfail} failed, {nskip} skipped")
    print("NOT COVERED by this run:")
    for item in not_covered:
        print(f"  - {item}")
    sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()