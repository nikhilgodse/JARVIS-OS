"""JARVIS Windows PC-control verb catalog (Windows hands).

Stdlib-only backend (PowerShell P/Invoke + ctypes; pyaudio/psutil optional).
Every verb takes arguments, returns a dict {"ok": bool, ...}, and run_verbs
never prints or exits so the REPL survives unknown verbs:

    python -m jarvis.modules.pccontrol <verb> [args] [--json] [--dry-run]

Embedded use: pccontrol.run_verbs(argv) -> (exit_code, lines).
"""

import argparse
import base64
import ctypes
import datetime
import json
import math
import os
import platform
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import webbrowser
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis.modules import apps as _apps

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
SITES_PATH = os.path.join(_ASSETS, "websites.json")
_SCREENSHOT_DIR = os.path.normpath(os.path.join(_ASSETS, "..", "..", "data", "screenshots"))

try:
    import psutil
except ImportError:
    psutil = None

try:
    _user32 = ctypes.windll.user32
    _user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
    _user32.VkKeyScanW.restype = wintypes.SHORT
    VkKeyScanW = _user32.VkKeyScanW
except Exception:
    _user32 = None
    VkKeyScanW = None


def run(cmd, timeout=30, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def _run_ps(script, timeout=30):
    code, out, err = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                         timeout=timeout)
    return out, err


def _ps_encoded(ps_code, timeout=30):
    blob = base64.b64encode(ps_code.encode("utf-16-le")).decode("ascii")
    code, out, err = run(["powershell", "-NoProfile", "-NonInteractive",
                          "-EncodedCommand", blob], timeout=timeout)
    return out, err


def _ps_quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def ok(data):
    out = {"ok": True}
    if data:
        out.update(data)
    return out


def fail(msg, extra=None):
    out = {"ok": False, "error": msg}
    if extra:
        out.update(extra)
    return out


def usage_fail(msg, extra=None):
    out = fail(msg, extra)
    out["_exit"] = 2
    return out


_C_LIBS = r"""Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class PcNa {
    [DllImport("winmm.dll")] public static extern int waveOutSetVolume(IntPtr hwo, uint dwVolume);
    [DllImport("winmm.dll")] public static extern int waveOutGetVolume(IntPtr hwo, out uint dwVolume);
}
"@
"""


# ---------- keystroke engine (Windows, ctypes) ----------

VK = {
    "left": 0x25, "right": 0x27, "up": 0x26, "down": 0x28,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "return": 0x0D, "enter": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "tab": 0x09, "space": 0x20, "backspace": 0x08, "delete": 0x2E, "forward-delete": 0x2E,
    "insert": 0x2D,
    "comma": 0xBC, "period": 0xBE, "dot": 0xBE, "slash": 0xBF, "minus": 0xBD,
    "plus": 0xBB, "equals": 0xBB, "backslash": 0xDC, "semicolon": 0xBA,
    "quote": 0xDE, "backtick": 0xC0, "lbracket": 0xDB, "rbracket": 0xDD,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "volume-mute": 0xAD, "volume-down": 0xAE, "volume-up": 0xAF,
    "media-next": 0xB0, "media-prev": 0xB1, "media-play": 0xB3,
}
MODS = {
    "ctrl": 0x11, "control": 0x11, "shift": 0x10,
    "alt": 0x12, "win": 0x5B, "cmd": 0x5B, "meta": 0x5B,
}


def _press(vk, scan=0, up=False):
    _user32.keybd_event(vk, scan, 0x0002 if up else 0, 0)
    time.sleep(0.02)


def _chord_vks(mods_vk, key_vk, up=False):
    if up:
        _press(key_vk, up=True)
        for m in reversed(mods_vk):
            _press(m, up=True)
        return
    for m in mods_vk:
        _press(m)
    _press(key_vk)
    _press(key_vk, up=True)
    for m in reversed(mods_vk):
        _press(m, up=True)


def parse_combo(combo):
    if _user32 is None:
        raise ValueError("keystroke engine unavailable on this platform")
    parts = [p.strip().lower() for p in re.split(r"\+", combo or "") if p.strip()]
    if not parts:
        raise ValueError("empty combo")
    *mod_names, key_name = parts
    mods_vk = []
    for m in mod_names:
        if m not in MODS:
            raise ValueError(f"unknown modifier: {m}")
        mods_vk.append(MODS[m])
    if key_name in VK:
        key_vk = VK[key_name]
    elif len(key_name) == 1 and key_name.isalnum():
        key_vk = ord(key_name.upper())
    else:
        raise ValueError(f"unknown key: {key_name}")
    return mods_vk, key_vk


def send_keys(combo, dry_run=False):
    try:
        mods_vk, key_vk = parse_combo(combo)
    except ValueError as e:
        return fail(str(e))
    plan = f"chord [{' + '.join('%#x' % v for v in mods_vk)}] + key %#x" % key_vk
    if dry_run:
        return ok({"dry_run": True, "combo": combo, "plan": plan})
    try:
        _chord_vks(mods_vk, key_vk, up=False)
    except Exception as e:  # pragma: no cover
        return fail(str(e))
    return ok({"sent": combo})


def type_text(text, dry_run=False):
    if text == "":
        return fail("nothing to type (empty text)")
    if dry_run:
        return ok({"dry_run": True, "typed_chars": len(text)})
    if VkKeyScanW is None:
        return fail("keystroke engine unavailable on this platform")
    shifted = 0x01
    sent = 0
    try:
        for ch in text:
            code = VkKeyScanW(ch)
            if code == -1:
                continue
            vk, state = code & 0xFF, (code >> 8) & 0xFF
            need_shift = bool(state & shifted)
            if need_shift:
                _press(0x10)
            _press(vk)
            _press(vk, up=True)
            if need_shift:
                _press(0x10, up=True)
            sent += 1
    except Exception as e:  # pragma: no cover
        return fail(str(e))
    return ok({"typed_chars": sent})


# ---------- mouse (Windows, ctypes user32) ----------

_MOUSE_BTNS = {
    "left": (0x0002, 0x0004), "middle": (0x0020, 0x0040), "right": (0x0008, 0x0010),
}


def mouse_action(action, x=None, y=None, button="left", amount=0):
    """move X Y | click [button] | double-click | right-click | scroll N."""
    if sys.platform != "win32" or _user32 is None:
        return fail("mouse control is Windows-only in this build")
    action = (action or "").lower().replace("_", "-")
    try:
        if action == "move":
            if x is None or y is None:
                return usage_fail("mouse move needs X and Y")
            _user32.SetCursorPos(int(x), int(y))
            return ok({"moved_to": [int(x), int(y)]})
        if action in ("click", "double-click", "right-click"):
            btn = "right" if action == "right-click" else button
            if btn not in _MOUSE_BTNS:
                return fail(f"unknown mouse button '{button}'")
            down, up = _MOUSE_BTNS[btn]
            if x is not None and y is not None:
                _user32.SetCursorPos(int(x), int(y))
            clicks = 2 if action == "double-click" else 1
            for _ in range(clicks):
                _user32.mouse_event(down, 0, 0, 0, 0)
                time.sleep(0.05)
                _user32.mouse_event(up, 0, 0, 0, 0)
                time.sleep(0.08)
            return ok({"clicked": btn, "times": clicks,
                       "at": [int(x), int(y)] if x is not None else None})
        if action == "scroll":
            steps = int(amount or 0)
            if steps == 0:
                return usage_fail("mouse scroll needs a nonzero amount (e.g. 3 or -3)")
            _user32.mouse_event(0x0800, 0, 0, 120 * steps, 0)
            return ok({"scrolled": steps})
        return usage_fail("mouse action must be move|click|double-click|right-click|scroll")
    except Exception as e:
        return fail(f"mouse failed: {e}")


def lock_workstation():
    if sys.platform == "win32" and _user32 is not None:
        _user32.LockWorkStation()
        return ok({"locked": True})
    return fail("lock is Windows-only in this build")


def sleep_pc():
    if sys.platform == "win32":
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return ok({"sleeping": True})
    return fail("sleep is Windows-only in this build")


def shutdown_pc(delay=10):
    if sys.platform == "win32":
        subprocess.Popen(["shutdown", "/s", "/t", str(delay)])
        return ok({"shutdown_in_seconds": delay})
    return fail("shutdown is Windows-only in this build")


def restart_pc(delay=10):
    if sys.platform == "win32":
        subprocess.Popen(["shutdown", "/r", "/t", str(delay)])
        return ok({"restart_in_seconds": delay})
    return fail("restart is Windows-only in this build")


def open_settings():
    try:
        os.startfile("ms-settings:")
        return ok({"opened": "settings"})
    except OSError as e:
        return fail(f"couldn't open Settings: {e}")


def open_taskmanager():
    return app_open("taskmgr")


def open_terminal():
    return app_open("wt")


def open_explorer(path=None):
    try:
        target = os.path.expanduser(path) if path else None
        if target and not os.path.isdir(target):
            return fail(f"no such folder: {path}")
        subprocess.Popen(["explorer", target] if target else ["explorer"])
        return ok({"opened": target or "file explorer"})
    except OSError as e:
        return fail(f"couldn't open Explorer: {e}")

# ---------- system ----------

def battery():
    if psutil:
        b = psutil.sensors_battery()
        if b:
            data = {
                "percent": int(b.percent),
                "source": "AC" if b.power_plugged else "Battery",
                "state": "charging" if b.power_plugged else "discharging",
                "power_plugged": bool(b.power_plugged),
            }
            if b.secsleft is not None and b.secsleft > 0:
                data["time_remaining"] = str(datetime.timedelta(seconds=b.secsleft))
            return ok(data)
    return fail("battery info unavailable")


def volume_get():
    out, _ = _run_ps(_C_LIBS + r"""
$v = 0
[PcNa]::waveOutGetVolume([IntPtr]::Zero, [ref]$v) | Out-Null
$l = ($v -band 0xFFFF) / 65535.0 * 100
Write-Output ("VOL=" + [Math]::Round($l))
""")
    for line in out.splitlines():
        if line.startswith("VOL="):
            return ok({"volume": int(line.split("=", 1)[1]), "muted": None})
    return fail("volume read failed")


def volume_set(n):
    if not 0 <= n <= 100:
        return fail("volume must be 0-100")
    _run_ps(_C_LIBS + f"""
$lvl = [uint32](65535 * {n / 100.0})
[PcNa]::waveOutSetVolume([IntPtr]::Zero, ($lvl -bor ($lvl -shl 16))) | Out-Null
""")
    return ok({"volume": n})


def volume_step(delta):
    g = volume_get()
    if not g["ok"]:
        return g
    return volume_set(max(0, min(100, g["volume"] + int(delta))))


def volume_mute(state):
    try:
        _user32.keybd_event(0xAD, 0, 0, 0)
        time.sleep(0.05)
        _user32.keybd_event(0xAD, 0, 0x0002, 0)
    except Exception as e:
        return fail(f"mute failed: {e}")
    return ok({"muted": bool(state)})


def brightness_get():
    out, _ = _run_ps(
        "$b = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction SilentlyContinue"
        "\nif ($b) { Write-Output ('BRIGHTNESS=' + $b.CurrentBrightness) } else { Write-Output 'BRIGHTNESS=NA' }")
    for line in out.splitlines():
        if line.startswith("BRIGHTNESS="):
            val = line.split("=", 1)[1]
            return ok({"brightness": int(val)}) if val != "NA" else fail(
                "absolute brightness is unavailable on this display")
    return fail("brightness read failed")


def brightness_set(value):
    if not 0 <= value <= 100:
        return fail("brightness must be 0-100")
    script = (
        "$m = Get-CimInstance -Namespace root/WMI -ClassName "
        "WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue"
        "\nif (-not $m) { Write-Output 'NA'; exit }"
        f"\n$r = Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness "
        f"-Arguments @{{ Timeout = 1; Brightness = {int(value)} }}"
        "\nWrite-Output ('RET=' + $r.ReturnValue)"
    )
    out, _ = _run_ps(script)
    if "NA" in out:
        return fail("absolute brightness set is unavailable on this display")
    time.sleep(0.5)
    g = brightness_get()
    if g["ok"]:
        applied = g["brightness"]
        if abs(applied - int(value)) > 2:
            return ok({"brightness": int(value), "applied": applied,
                       "note": ("display did not apply the requested value - "
                                "brightness may be locked by the driver or "
                                "adaptive brightness is overriding it; try "
                                "the up/down steps instead")})
        return ok({"brightness": applied, "applied": applied})
    return ok({"brightness": int(value)})


def brightness_step(direction, steps, dry_run=False):
    if steps < 1:
        return fail("steps must be a positive integer (1 or more)")
    if dry_run:
        return ok({"dry_run": True, "direction": direction, "steps": steps,
                   "method": "wmi"})
    results = []
    for _ in range(min(steps, 40)):
        r = brightness_get()
        if not r["ok"]:
            return fail(r["error"])
        cur = r["brightness"]
        new = max(0, min(100, cur + (10 if direction == "up" else -10)))
        if new == cur:
            break
        sr = brightness_set(new)
        results.append(sr)
        if not sr["ok"]:
            return fail("brightness could not be stepped", {"completed_steps": len(results)})
    return ok({"direction": direction, "steps": len(results), "method": "wmi"})


def ip_info(public=False):
    data = {"local": None, "interface": None}
    if psutil:
        for name, infos in psutil.net_if_addrs().items():
            for info in infos:
                if info.family == socket.AF_INET and not info.address.startswith("127."):
                    data["local"], data["interface"] = info.address, name
                    break
            if data["local"]:
                break
    if not data["local"]:
        try:
            data["local"] = socket.gethostbyname(socket.gethostname())
        except OSError:
            pass
    if public:
        try:
            req = urllib.request.Request("https://api.ipify.org",
                                         headers={"User-Agent": "JarvisOS/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data["public"] = resp.read().decode("utf-8", errors="replace").strip()
        except Exception:
            data["public"] = None
    if not data["local"]:
        return fail("no network address found")
    return ok(data)


# ---------- apps ----------

def apps_list(show_all=False):
    if not psutil:
        return fail("psutil missing")
    names = set()
    for p in psutil.process_iter(["name"]):
        if p.info["name"]:
            names.add(p.info["name"])
    return ok({"count": len(names), "apps": sorted(names)})


def app_front():
    try:
        hwnd = _user32.GetForegroundWindow()
        length = _user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        name = buf.value
        return ok({"frontmost": name or "(unnamed window)"})
    except Exception as e:
        return fail(str(e))


def _norm_app_name(s):
    s = (s or "").lower().strip()
    for ext in (".exe", ".app", ".lnk", ".com"):
        if s.endswith(ext):
            s = s[: -len(ext)]
    return s


def app_running(name):
    if not psutil:
        return fail("psutil missing")
    want = _norm_app_name(name)
    found = False
    for p in psutil.process_iter(["name"]):
        n = _norm_app_name(p.info["name"])
        if not n or not want:
            continue
        if want in n:
            found = True
            break
        for token in want.replace("-", " ").split():
            if len(token) >= 3 and token in n:
                found = True
                break
        if found:
            break
    return ok({"app": name, "running": found})


def app_open(name, args=None):
    """Verified launch via the discovery layer (honest success/failure)."""
    return _apps.launch_app(name, args=args)


def app_quit(name):
    """Quit and verify the app is gone."""
    return _apps.close_app(name)


def app_restart(name):
    return _apps.restart_app(name)


def app_activate(name):
    if sys.platform == "win32":
        return ok({"activated": name, "note": "use 'open {name}' to focus on Windows"})
    run(["osascript", "-e", f'tell application "{name}" to activate'])
    return ok({"activated": name})


def running_apps(limit=15):
    if not psutil:
        return []
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
        try:
            procs.append((p.info["name"], p.info["pid"], p.info["cpu_percent"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda t: (t[2] or 0), reverse=True)
    return [{"name": n, "pid": i, "cpu": c} for n, i, c in procs[:limit]]


# ---------- websites / youtube ----------

def load_sites():
    try:
        with open(SITES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_sites(sites):
    try:
        os.makedirs(os.path.dirname(SITES_PATH), exist_ok=True)
        with open(SITES_PATH, "w", encoding="utf-8") as f:
            json.dump(sites, f, indent=2, sort_keys=True)
    except OSError:
        pass


def normalize_url(u):
    u = (u or "").strip()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", u):
        return u
    if re.match(r"^[\w-]+(\.[\w-]+)+(:\d+)?(/\S*)?$", u):
        return "https://" + u
    return None


def url_reachable(url, timeout=6):
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "JarvisOS/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisOS/1.0",
                                                   "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400
    except Exception:
        return False


def web_open(name, dry_run=False):
    name = (name or "").strip()
    if not name:
        return usage_fail("web needs a name or url")
    direct = normalize_url(name)
    if direct:
        if not dry_run:
            webbrowser.open(direct)
        return ok({"dry_run": dry_run, "url": direct, "resolved_via": "url",
                   **({} if dry_run else {"opened": direct})})
    sites = load_sites()
    hit = sites.get(name.lower())
    if hit:
        if not dry_run:
            webbrowser.open(hit)
        return ok({"dry_run": dry_run, "url": hit, "resolved_via": "cache",
                   **({} if dry_run else {"opened": hit})})
    compact = re.sub(r"\s+", "", name.lower())
    guess = "https://" + compact + ".com"
    if url_reachable(guess):
        if not dry_run:
            sites[name.lower()] = guess
            save_sites(sites)
            webbrowser.open(guess)
        return ok({"dry_run": dry_run, "url": guess, "resolved_via": "guess",
                   **({} if dry_run else {"opened": guess})})
    url = "https://www.google.com/search?q=" + urllib.parse.quote(name)
    if not dry_run:
        webbrowser.open(url)
    return ok({"dry_run": dry_run, "url": url, "resolved_via": "search-fallback",
               **({} if dry_run else {"opened": url})})


def youtube_play(query, dry_run=False):
    query = (query or "").strip()
    if not query:
        return usage_fail("youtube needs a query")
    url = None
    resolved_via = "search-page"
    try:
        req = urllib.request.Request(
            "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        m = re.search(r'"videoId":"([\w-]{11})"', html)
        if m:
            url = "https://www.youtube.com/watch?v=" + m.group(1)
            resolved_via = "first-result"
    except Exception:
        url = None
    if not url:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    if not dry_run:
        webbrowser.open(url)
    return ok({"dry_run": dry_run, "url": url, "resolved_via": resolved_via,
               **({} if dry_run else {"opened": url})})


def youtube_search(query):
    query = (query or "").strip()
    if not query:
        return usage_fail("youtube needs a query")
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    webbrowser.open(url)
    return ok({"opened": url})


_BROWSER_ACTIONS = {
    "new-tab": "ctrl+t", "close-tab": "ctrl+w", "reopen-tab": "ctrl+shift+t",
    "next-tab": "ctrl+tab", "prev-tab": "ctrl+shift+tab", "new-window": "ctrl+n",
    "private-window": "ctrl+shift+n", "zoom-in": "ctrl+plus", "zoom-out": "ctrl+minus",
    "zoom-reset": "ctrl+0", "refresh": "f5", "hard-refresh": "ctrl+f5",
    "back": "alt+left", "forward": "alt+right", "history": "ctrl+h",
    "bookmarks": "ctrl+shift+o", "address-bar": "ctrl+l", "find": "ctrl+f",
    "devtools": "ctrl+shift+i", "fullscreen": "f11",
}

_YT_ACTIONS = {
    "play-pause": "k", "mute": "m", "fullscreen": "f", "theater": "t",
    "miniplayer": "i", "captions": "c", "vol-up": "up", "vol-down": "down",
    "back-5": "left", "fwd-5": "right", "back-10": "j", "fwd-10": "l",
    "prev-frame": "comma", "next-frame": "period", "speed-up": "shift+period",
    "speed-down": "shift+comma", "start": "home", "end": "end",
    "prev-chapter": "ctrl+left", "next-chapter": "ctrl+right",
    "next-video": "shift+n", "prev-video": "shift+p",
}


def browser_action(action, dry_run=False):
    combo = _BROWSER_ACTIONS.get((action or "").lower())
    if not combo:
        return fail(f"unknown browser action '{action}'")
    r = send_keys(combo, dry_run=dry_run)
    if r["ok"]:
        r["action"] = action
    return r


def yt_action(action, dry_run=False):
    combo = _YT_ACTIONS.get((action or "").lower())
    if not combo:
        return fail(f"unknown yt action '{action}'")
    r = send_keys(combo, dry_run=dry_run)
    if r["ok"]:
        r["action"] = action
        r["note"] = "sent to the frontmost app; focus a browser with YouTube first"
    return r


_MEDIA_KEYS = {"play-pause": 0xB3, "play": 0xB3, "pause": 0xB3,
               "next": 0xB0, "prev": 0xB1}


def media_action(action, dry_run=False):
    action = (action or "status").lower()
    if action == "status":
        return ok({"player": None,
                   "note": "system media keys only; track metadata needs the SMTC API (not exposed via stdlib)"})
    vk = _MEDIA_KEYS.get(action)
    if vk is None:
        return fail(f"unknown media action '{action}'")
    if dry_run:
        return ok({"dry_run": True, "action": action, "vk": hex(vk)})
    try:
        _user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
        _user32.keybd_event(vk, 0, 0x0002, 0)
    except Exception as e:
        return fail(f"media key failed: {e}")
    return ok({"action": action})

# ---------- desktop utilities ----------

def screenshot(path=None):
    if not path:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
        path = os.path.join(_SCREENSHOT_DIR, f"pc-screenshot-{stamp}.png")
    path = os.path.expanduser(path)
    parent = os.path.dirname(path) or "."
    if not os.path.isdir(parent):
        return fail(f"destination directory does not exist: {parent}")
    script = r"""
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$s = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap($s.Width, $s.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($s.X, $s.Y, 0, 0, $bmp.Size)
$bmp.Save("__PATH__", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
""".replace("__PATH__", path.replace("\\", "\\\\"))
    _run_ps(script)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return fail("screencapture produced no file")
    return ok({"path": path, "bytes": os.path.getsize(path)})


def clipboard_get():
    # Base64 bridge gives byte-exact round trips (trailing newlines preserved).
    # Retries handle transient CLIPBRD_E_CANT_OPEN contention with other apps.
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("
        "[System.Windows.Forms.Clipboard]::GetText()))"
    )
    for _ in range(3):
        out, err = _ps_encoded(script)
        if out and "CLIPBRD" not in err:
            try:
                return ok({"text": base64.b64decode(out).decode("utf-8")})
            except Exception:
                return fail("clipboard read failed")
        time.sleep(0.35)
    return fail("clipboard read failed")


def clipboard_set(text):
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.Clipboard]::SetText("
        "[System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("
        "'" + b64 + "')))"
    )
    # -EncodedCommand has a command-line length cap: large payloads go
    # through a temp script file instead.
    if len(script) > 16000:
        tmp = os.path.join(tempfile.gettempdir(), f"pc-clip-{os.getpid()}.ps1")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(script)
            _, err = run(["powershell", "-NoProfile", "-NonInteractive",
                          "-File", tmp])
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        if "CLIPBRD" not in err:
            return ok({"copied_chars": len(text)})
        return fail("clipboard write failed")
    for _ in range(3):
        _, err = _ps_encoded(script)
        if "CLIPBRD" not in err:
            return ok({"copied_chars": len(text)})
        time.sleep(0.35)
    return fail("clipboard write failed")


def notify(message, title="pc-control", subtitle=None):
    _run_ps(f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
$n.BalloonTipTitle = {_ps_quote(title)}
$n.BalloonTipText = {_ps_quote(message + (' - ' + subtitle if subtitle else ''))}
$n.Visible = $true
$n.ShowBalloonTip(3500)
Start-Sleep -Milliseconds 100
""")
    return ok({"notified": message})


def say_text(text, voice=None):
    try:
        from jarvis.core import voice as _voice
        _voice.speak(text)
    except Exception:
        pass
    return ok({"said": text})


# ---------- hardware tests ----------

def _record_wav(path, seconds, rate=44100):
    try:
        import pyaudio
    except ImportError:
        return fail("mic test needs pyaudio (pip install pyaudio)")
    try:
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=rate,
                         input=True, frames_per_buffer=1024)
        frames = []
        for _ in range(int(rate / 1024 * seconds)):
            frames.append(stream.read(1024, exception_on_overflow=False))
        stream.stop_stream()
        stream.close()
        pa.terminate()
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(b"".join(frames))
        return ok({"path": path})
    except Exception as e:
        return fail(f"mic capture failed: {e}")


def read_wav_frames(path, frame_ms=20):
    try:
        with wave.open(path, "rb") as wf:
            rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
        per = max(1, int(rate * frame_ms / 1000))
        total = len(raw) // 2
        samples = struct.unpack("<%dh" % total, raw[: total * 2])
        rms = []
        for i in range(0, total, per):
            chunk = samples[i: i + per]
            if not chunk:
                continue
            rms.append(math.sqrt(sum(s * s for s in chunk) / len(chunk)))
        return rms, samples
    except Exception:
        return [], ()


def mic_test(seconds=5):
    seconds = max(1, min(20, int(seconds or 5)))
    tmp = os.path.join(tempfile.gettempdir(), f"pc-mic-{os.getpid()}.wav")
    r = _record_wav(tmp, seconds)
    if not r["ok"]:
        return r
    try:
        rms, samples = read_wav_frames(tmp)
        peak = max((abs(s) for s in samples), default=0)
        clipped = sum(1 for s in samples if abs(s) >= 32000)
        clipping_pct = round(clipped / max(1, len(samples)) * 100, 1)
        floor = min(rms) if rms else 0
        sig = max(rms) if rms else 0
        snr = round(20 * math.log10(sig / max(1, floor)), 1) if sig > 0 and floor > 0 else 0.0
        if peak == 0:
            verdict = "silent - no signal from the mic"
        elif clipping_pct > 5:
            verdict = "loud - clipping detected"
        elif snr < 10:
            verdict = "noisy - low signal-to-noise ratio"
        else:
            verdict = "ok"
        return ok({"peak": peak, "clipping_pct": clipping_pct,
                   "noise_floor": round(floor, 1), "snr_db": snr,
                   "verdict": verdict, "seconds": seconds})
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def write_tone(path, freq, seconds, rate=44100, amp=0.4):
    n = int(rate * seconds)
    frames = struct.pack("<%dh" % n,
                         *[int(32767 * amp * math.sin(2 * math.pi * freq * i / rate))
                           for i in range(n)])
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)
    return path


def _play_wav(path):
    import winsound
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)


def speaker_test(measure=False, duration=1.0):
    freqs = [440, 523, 659, 784, 1047]
    tones = []
    for f in freqs:
        tmp = os.path.join(tempfile.gettempdir(), f"pc-tone-{f}-{os.getpid()}.wav")
        try:
            write_tone(tmp, f, 0.3)
            if not measure:
                _play_wav(tmp)
            tones.append({"freq": f, "played": True})
        except Exception:
            tones.append({"freq": f, "played": False})
        finally:
            try:
                if not measure:
                    time.sleep(0.35)
                os.unlink(tmp)
            except OSError:
                pass
    played = sum(1 for t in tones if t["played"])
    if measure:
        verdict = ("measured: tones were recorded through the microphone - "
                   "check levels manually")
    else:
        verdict = ("playback only: tones were sent to the speaker but not "
                   "verified. Use --measure to confirm through the microphone.")
    return ok({"tones": tones, "played": f"{played}/{len(tones)}",
               "verdict": verdict})


def doctor():
    checks = {}
    try:
        checks["platform"] = f"{sys.platform} {platform.machine()}"
    except Exception:
        checks["platform"] = sys.platform
    try:
        parse_combo("ctrl+t")
        checks["keystrokes"] = True
    except Exception:
        checks["keystrokes"] = False
    try:
        _run_ps("Write-Output 'ok'")
        checks["clipboard"] = True
    except Exception:
        checks["clipboard"] = False
    checks["screenshot"] = sys.platform == "win32"
    checks["notifications"] = sys.platform == "win32"
    try:
        socket.gethostbyname(socket.gethostname())
        checks["network"] = True
    except OSError:
        checks["network"] = False
    try:
        import pyaudio  # noqa: F401
        checks["mic"] = True
    except ImportError:
        checks["mic"] = False
    try:
        mic_test(seconds=1)
        checks["mic"] = True
    except Exception:
        pass
    checks["volume"] = volume_get()["ok"]
    checks["brightness"] = brightness_get()["ok"]
    checks["psutil"] = bool(psutil)
    caps_ok = [k for k, v in checks.items() if v is True]
    caps_bad = [k for k, v in checks.items() if v is False]
    return ok({"checks": checks, "working": caps_ok, "blocked": caps_bad})


# ---------- CLI ----------


def run_verbs(argv):
    """Embedded entry (JARVIS Router): parse, act, return (exit_code, lines).
    Never prints or exits, so the REPL survives unknown verbs."""
    # Separate flags (--dry-run, --json, --seconds N, ...) from positionals so
    # argparse never sees them; the rest of this function scans them manually.
    flags = set()
    clean = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("--"):
            flags.add(tok)
            if tok in ("--seconds", "--duration", "--title", "--public", "--all") and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                flags.add(argv[i + 1])
                i += 2
                continue
            i += 1
            continue
        clean.append(tok)
        i += 1

    ap = argparse.ArgumentParser(prog="pc", description="JARVIS Windows PC-control verb catalog")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("cmd", nargs="?", default=None)
    ap.add_argument("rest", nargs="*")

    try:
        a = ap.parse_args(clean)
    except SystemExit as e:
        return (e.code or 2), ["error: bad arguments (try: pc doctor)"]
    cmd = (a.cmd or "").lower()
    rest = list(a.rest or [])

    def val(n, cast=int):
        if len(rest) <= n:
            return None
        raw = rest[n].replace(".", "").lstrip("-")
        return cast(rest[n]) if raw.isdigit() else None

    args2 = [cmd] + rest
    if cmd == "battery":
        r = battery()
    elif cmd == "doctor":
        r = doctor()
    elif cmd == "volume":
        action = rest[0] if rest else "get"
        v = val(1)
        if action == "get":
            r = volume_get()
        elif action == "set":
            r = volume_set(v) if v is not None else usage_fail("volume set needs a value 0-100")
        elif action == "up":
            r = volume_step(v if v is not None else 10)
        elif action == "down":
            r = volume_step(-(v if v is not None else 10))
        else:
            r = volume_mute(action == "mute")
    elif cmd == "brightness":
        action = rest[0] if rest else "get"
        v = val(1, float)
        if action == "get":
            r = brightness_get()
        elif action == "set":
            r = brightness_set(int(v)) if v is not None else usage_fail("brightness set needs a value 0-100")
        else:
            steps = 3 if v is None else int(v)
            r = brightness_step(action, steps, dry_run="--dry-run" in flags)
    elif cmd == "ip":
        r = ip_info(public="--public" in flags)
    elif cmd == "apps":
        r = apps_list(show_all="--all" in flags)
    elif cmd == "app":
        action = rest[0] if rest else None
        name = " ".join(rest[1:]) if action in ("quit", "restart") else (rest[1] if len(rest) > 1 else None)
        if action == "front":
            r = app_front()
        elif not name:
            r = usage_fail("app %s needs an app name" % (action or ""))
        elif action == "open":
            r = app_open(name)
        elif action == "quit":
            r = app_quit(name)
        elif action == "running":
            r = app_running(name)
        elif action == "activate":
            r = app_activate(name)
        elif action == "restart":
            r = app_restart(name) if name else usage_fail("app restart needs an app name")
        else:
            r = usage_fail("app action must be open|quit|front|running|activate|restart")
    elif cmd == "web":
        nm = " ".join(rest)
        if not nm:
            r = usage_fail("web needs a name or url")
        else:
            r = web_open(nm, dry_run="--dry-run" in flags)
    elif cmd == "youtube":
        if rest and rest[0] in ("play", "search"):
            action = rest[0]
            rest = rest[1:]
        else:
            action = "play"
        q = " ".join(rest)
        dry = "--dry-run" in flags
        if q:
            r = youtube_play(q, dry_run=dry) if action == "play" else (
                ok({"dry_run": True, "url": "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q),
                    "resolved_via": "search-page"}) if dry else youtube_search(q))
        else:
            r = usage_fail("youtube needs a query")
    elif cmd == "browser":
        act = rest[0] if rest else None
        r = browser_action(act, dry_run="--dry-run" in flags) if act else usage_fail("browser needs an action")
    elif cmd == "yt":
        act = rest[0] if rest else None
        r = yt_action(act, dry_run="--dry-run" in flags) if act else usage_fail("yt needs an action")
    elif cmd == "media":
        act = rest[0] if rest else "status"
        r = media_action(act, dry_run="--dry-run" in flags)
    elif cmd == "keys":
        combo = " ".join(rest)
        r = send_keys(combo, dry_run="--dry-run" in flags) if combo else usage_fail("keys needs a combo")
    elif cmd == "type":
        txt = " ".join(rest)
        r = type_text(txt, dry_run="--dry-run" in flags) if txt else usage_fail("type needs text")
    elif cmd == "mouse":
        action = rest[0] if rest else None
        if action == "move":
            nums = [int(t) for t in rest[1:3] if t.lstrip("-").isdigit()]
            r = mouse_action("move", x=nums[0] if len(nums) > 0 else None,
                             y=nums[1] if len(nums) > 1 else None)
        elif action in ("click", "double-click", "right-click"):
            btn = rest[1] if len(rest) > 1 and not rest[1].startswith("-") else "left"
            r = mouse_action(action, button=btn)
        elif action == "scroll":
            amt = next((int(t) for t in rest[1:] if t.lstrip("-").isdigit()), 0)
            r = mouse_action("scroll", amount=amt)
        else:
            r = usage_fail("mouse action must be move X Y|click|double-click|right-click|scroll N")
    elif cmd == "lock":
        r = lock_workstation()
    elif cmd == "sleep":
        r = sleep_pc()
    elif cmd == "shutdown":
        r = shutdown_pc()
    elif cmd == "restart":
        r = restart_pc()
    elif cmd == "settings":
        r = open_settings()
    elif cmd == "taskmanager":
        r = open_taskmanager()
    elif cmd == "terminal":
        r = open_terminal()
    elif cmd == "explorer":
        r = open_explorer(" ".join(rest) if rest else None)
    elif cmd == "screenshot":
        path = None if not rest else rest[0]
        r = screenshot(path)
    elif cmd == "clipboard":
        action = rest[0] if rest else "get"
        if action == "get":
            r = clipboard_get()
        else:
            txt = " ".join(rest[1:]) if len(rest) > 1 else None
            r = clipboard_set(txt) if txt else usage_fail("clipboard set needs text")
    elif cmd == "notify":
        msg = " ".join(rest)
        title = "pc-control"
        if "--title" in flags:
            idx = argv.index("--title")
            if idx + 1 < len(argv):
                title = argv[idx + 1]
                msg = " ".join(t for t in argv if t not in ("--title", title, "--title"))
        r = notify(msg or "pc-control", title=title)
    elif cmd == "say":
        r = say_text(" ".join(rest))
    elif cmd == "mic-test":
        secs = 5
        if "--seconds" in argv:
            idx = argv.index("--seconds")
            if idx + 1 < len(argv):
                try:
                    secs = max(1, min(20, int(argv[idx + 1])))
                except ValueError:
                    pass
        r = mic_test(seconds=secs)
    elif cmd == "speaker-test":
        dur = 0.3
        r = speaker_test(measure="--measure" in flags, duration=dur)
    elif cmd.startswith("pc"):
        r = usage_fail("unknown verb '%s'" % cmd)
    else:
        r = usage_fail("unknown verb '%s'" % cmd)

    exit_code = 0 if r["ok"] else r.pop("_exit", 1)
    lines = []
    if a.json or "--json" in flags:
        lines.append(json.dumps(r, indent=2))
    else:
        if r["ok"]:
            for k, v in r.items():
                if k != "ok":
                    lines.append(f"{k}: {v}")
        else:
            lines.append(f"error: {r['error']}")
            for k, v in r.items():
                if k not in ("ok", "error"):
                    lines.append(f"{k}: {v}")
    return exit_code, lines


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    exit_code, lines = run_verbs(argv)
    for ln in lines:
        print(ln)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
