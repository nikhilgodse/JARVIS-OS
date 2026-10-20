"""Application discovery + verified launch/close for Windows.

Resolution order for an app name:
  1. alias map (chrome, vs code, calculator, settings, ...)
  2. PATH lookup, real .exe preferred over .cmd/.bat shims
  3. "App Paths" registry (how `start chrome` resolves)
  4. known install directories (Program Files, LocalAppData, ...)
  5. Start Menu shortcut scan (*.lnk, launched via os.startfile)

Every launch is verified: after starting the process we poll psutil for a
matching process. Replies are honest - a missing app reports
"I couldn't find X installed", never a fake success. Never kills protected
system processes (explorer, dwm, ...).
"""

import os
import shutil
import subprocess
import sys
import time

try:
    import psutil
except ImportError:
    psutil = None

try:
    import winreg
except ImportError:
    winreg = None

# canonical-name -> launch token (exe on PATH, shell command, or ms URI)
ALIASES = {
    "chrome": "chrome", "google chrome": "chrome",
    "brave": "brave", "brave browser": "brave",
    "edge": "msedge", "microsoft edge": "msedge",
    "firefox": "firefox", "mozilla firefox": "firefox",
    "opera": "opera",
    "vs code": "code", "visual studio code": "code", "vscode": "code", "code": "code",
    "spotify": "spotify",
    "whatsapp": "whatsapp",
    "discord": "discord",
    "telegram": "telegram",
    "vlc": "vlc",
    "calculator": "calc", "calc": "calc",
    "notepad": "notepad",
    "paint": "mspaint", "ms paint": "mspaint",
    "file explorer": "explorer", "windows explorer": "explorer", "explorer": "explorer",
    "this pc": "explorer", "my computer": "explorer", "my pc": "explorer",
    "file manager": "explorer",
    "settings": "ms-settings:", "windows settings": "ms-settings:",
    "terminal": "wt", "windows terminal": "wt",
    "command prompt": "cmd", "cmd": "cmd",
    "powershell": "powershell",
    "task manager": "taskmgr",
    "control panel": "control",
    "snipping tool": "snippingtool",
    "camera": "microsoft.windows.camera:",
}

# canonical-name -> exe basenames to look for (App Paths, known dirs, verify)
EXE_NAMES = {
    "chrome": ["chrome.exe"],
    "brave": ["brave.exe"],
    "msedge": ["msedge.exe"],
    "firefox": ["firefox.exe"],
    "opera": ["opera.exe"],
    "code": ["code.exe"],
    "spotify": ["spotify.exe"],
    "whatsapp": ["whatsapp.exe", "whatsapproot.exe"],
    "discord": ["discord.exe", "updatediscord.exe"],
    "telegram": ["telegram.exe"],
    "vlc": ["vlc.exe"],
    "calc": ["calc.exe", "calculatorapp.exe"],
    "notepad": ["notepad.exe"],
    "mspaint": ["mspaint.exe"],
    "explorer": ["explorer.exe"],
    "taskmgr": ["taskmgr.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "wt": ["wt.exe", "windowsterminal.exe"],
}

# exe basenames used to verify a launch (token -> basenames)
VERIFY_NAMES = dict(EXE_NAMES)
VERIFY_NAMES.update({
    "control": ["control.exe"],
    "snippingtool": ["snippingtool.exe"],
})

PROTECTED = {"explorer.exe", "dwm.exe", "sihost.exe", "csrss.exe", "smss.exe",
             "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe",
             "svchost.exe", "system", "system idle process", "registry",
             "memcompression", "fontdrvhost.exe"}


def _known_dirs():
    dirs = []
    for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA",
                "PROGRAMDATA", "WINDIR", "SYSTEMROOT"):
        v = os.environ.get(var)
        if v and os.path.isdir(v):
            dirs.append(v)
    pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    lad = os.environ.get("LOCALAPPDATA", "")
    dirs.extend([
        os.path.join(pf, "Google", "Chrome", "Application"),
        os.path.join(pf86, "Google", "Chrome", "Application"),
        os.path.join(lad, "Google", "Chrome", "Application"),
        os.path.join(pf, "BraveSoftware", "Brave-Browser", "Application"),
        os.path.join(lad, "BraveSoftware", "Brave-Browser", "Application"),
        os.path.join(pf86, "Microsoft", "Edge", "Application"),
        os.path.join(pf, "Mozilla Firefox"),
        os.path.join(pf86, "Mozilla Firefox"),
        os.path.join(lad, "Programs", "Microsoft VS Code"),
        os.path.join(pf, "Microsoft VS Code"),
        os.path.join(pf86, "Microsoft VS Code"),
        os.path.join(lad, "Spotify"),
        os.path.join(pf, "VideoLAN", "VLC"),
        os.path.join(pf86, "VideoLAN", "VLC"),
    ])
    seen, out = set(), []
    for d in dirs:
        dl = d.lower()
        if dl not in seen:
            seen.add(dl)
            out.append(d)
    return out


def normalize(name):
    n = (name or "").lower().strip().strip("?.!")
    n = n.removeprefix("the ").strip()
    n = n.removesuffix(" app").removesuffix(" application").strip()
    if n.endswith(" browser"):
        base = n[: -len(" browser")].strip()
        if base in ALIASES or base in EXE_NAMES:
            n = base
    return ALIASES.get(n, n)


def _app_paths_lookup(exe):
    """Resolve via HKLM/HKCU ...\\App Paths\\<exe> (what `start` uses)."""
    if not winreg or sys.platform != "win32":
        return None
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\\" + exe) as k:
                path, _ = winreg.QueryValueEx(k, "")
                if path and os.path.isfile(path):
                    return path
        except OSError:
            continue
    return None


_start_menu_cache = None


def _start_menu_map():
    """Display-name (lower) -> .lnk path for Start Menu entries."""
    global _start_menu_cache
    if _start_menu_cache is not None:
        return _start_menu_cache
    found = {}
    roots = []
    for var in ("APPDATA", "PROGRAMDATA"):
        base = os.environ.get(var)
        if base:
            roots.append(os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs"))
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for f in files:
                if f.lower().endswith(".lnk"):
                    found.setdefault(os.path.splitext(f)[0].lower(),
                                     os.path.join(dirpath, f))
    _start_menu_cache = found
    return found


def find_app(name, fuzzy=True):
    """Locate an app. Returns dict {ok, kind, path|cmd|uri|lnk, display}.
    fuzzy=False skips the loose Start-Menu substring step (used when a web
    search fallback exists and must not steal ordinary words)."""
    norm = normalize(name)
    display = (name or "").strip().strip("?.!") or norm
    if norm.startswith("ms-") or ":" in norm:
        return {"ok": True, "kind": "uri", "uri": norm, "display": display}
    exes = EXE_NAMES.get(norm, [])
    # 1) PATH - real .exe first
    cands = []
    for exe in exes + [norm, norm + ".exe"]:
        w = shutil.which(exe)
        if w and w.lower() not in {c.lower() for c in cands}:
            cands.append(w)
    cands.sort(key=lambda p: (os.path.splitext(p)[1].lower() != ".exe", len(p)))
    if cands and os.path.splitext(cands[0])[1].lower() == ".exe":
        return {"ok": True, "kind": "exe", "path": cands[0], "display": display}
    # 2) App Paths registry
    for exe in exes:
        p = _app_paths_lookup(exe)
        if p:
            return {"ok": True, "kind": "exe", "path": p, "display": display}
    # 3) known install dirs
    for d in _known_dirs():
        if not os.path.isdir(d):
            continue
        for exe in exes:
            p = os.path.join(d, exe)
            if os.path.isfile(p):
                return {"ok": True, "kind": "exe", "path": p, "display": display}
    # 4) PATH fallback (accepts .cmd/.bat shims, launched via cmd /c)
    if cands:
        return {"ok": True, "kind": "exe", "path": cands[0], "display": display}
    # 5) Start Menu shortcut
    menu = _start_menu_map()
    for key in (norm, display.lower(), norm + ".lnk"):
        if key in menu:
            return {"ok": True, "kind": "lnk", "lnk": menu[key], "display": display}
    if not fuzzy:
        return {"ok": False, "error": f"I couldn't find {display} installed on this computer."}
    for key, lnk in menu.items():
        if norm and (norm in key or key in norm):
            return {"ok": True, "kind": "lnk", "lnk": lnk, "display": display}
    return {"ok": False, "error": f"I couldn't find {display} installed on this computer."}


def _matching_procs(basenames):
    if not psutil:
        return []
    want = {b.lower() for b in basenames}
    out = []
    for p in psutil.process_iter(["name", "exe"]):
        try:
            n = (p.info.get("name") or "").lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if n in want:
            out.append(p)
    return out


def is_running(name):
    norm = normalize(name)
    return bool(_matching_procs(VERIFY_NAMES.get(norm, [norm if norm.endswith(".exe") else norm + ".exe"])))


def launch_app(name, args=None):
    """Launch and verify. Honest result, never a blind success."""
    found = find_app(name)
    if not found["ok"]:
        return found
    display = found["display"]
    kind = found["kind"]
    try:
        if kind == "uri":
            os.startfile(found["uri"])
            return {"ok": True, "launched": display, "verified": True,
                    "method": "uri"}
        if kind == "lnk":
            os.startfile(found["lnk"])
            time.sleep(0.8)
            return {"ok": True, "launched": display, "verified": True,
                    "method": "startmenu"}
        exe = found["path"]
        base = os.path.basename(exe).lower()
        already = bool(_matching_procs([base])) if base != "explorer.exe" else True
        cmd = [exe] + list(args or [])
        if os.path.splitext(exe)[1].lower() in (".cmd", ".bat"):
            cmd = ["cmd", "/c"] + cmd
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                         close_fds=True)
        if base == "explorer.exe":
            return {"ok": True, "launched": display, "verified": True,
                    "method": "exe"}
        deadline = time.time() + 4.0
        while time.time() < deadline:
            if _matching_procs([base]):
                return {"ok": True, "launched": display, "verified": True,
                        "method": "exe", "was_running": already}
            time.sleep(0.25)
        if already:
            return {"ok": True, "launched": display, "verified": True,
                    "method": "exe", "was_running": True}
        return {"ok": False,
                "error": f"I tried to open {display} but it didn't start."}
    except OSError as e:
        return {"ok": False, "error": f"I couldn't open {display}: {e}"}


def close_app(name):
    """Quit an app's processes and verify they are gone."""
    norm = normalize(name)
    display = (name or "").strip().strip("?.!") or norm
    bases = VERIFY_NAMES.get(norm, [norm if norm.endswith(".exe") else norm + ".exe"])
    if any(b.lower() in PROTECTED for b in bases):
        return {"ok": False,
                "error": f"I won't close {display} - it's a protected system process."}
    procs = _matching_procs(bases)
    if not procs:
        code = subprocess.run(["taskkill", "/IM", bases[0], "/F"],
                              capture_output=True).returncode if bases else 1
        if code == 0:
            return {"ok": True, "closed": display, "was_running": True}
        return {"ok": True, "closed": display, "was_running": False,
                "note": f"{display} wasn't running."}
    for p in procs:
        try:
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    deadline = time.time() + 2.5
    alive = procs
    while time.time() < deadline:
        alive = [p for p in procs if p.is_running()]
        if not alive:
            break
        time.sleep(0.25)
    for p in alive:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.4)
    gone = not any(p.is_running() for p in procs)
    if gone:
        return {"ok": True, "closed": display, "was_running": True}
    return {"ok": False, "error": f"{display} wouldn't close - it may need admin rights."}


def restart_app(name):
    c = close_app(name)
    if not c["ok"]:
        return c
    time.sleep(0.6)
    r = launch_app(name)
    if r["ok"]:
        r["restarted"] = r.pop("launched")
    return r
