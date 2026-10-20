import shutil
import subprocess
import sys

from ..core import speaker

COMMON_APPS = {
    "notepad": "notepad",
    "calculator": "calc",
    "paint": "mspaint",
    "cmd": "cmd",
    "powershell": "powershell",
    "explorer": "explorer",
    "edge": "msedge",
}


def launch(name):
    if not name:
        speaker.error_msg("Provide an application name.")
        return
    app = COMMON_APPS.get(name.lower(), name)
    speaker.line(f'Launching "{app}"...')
    try:
        if sys.platform == "win32":
            subprocess.Popen(["start", "", app], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", app])
        else:
            subprocess.Popen(app, shell=True)
        speaker.success_msg(f"Launched {name}.")
    except OSError as e:
        speaker.error_msg(f"Failed to launch '{name}': {e}")


def known_apps():
    speaker.header("KNOWN APPLICATIONS")
    pad = max(len(n) for n in COMMON_APPS) if COMMON_APPS else 1
    for name, exe in COMMON_APPS.items():
        speaker.raw(f"  {name.ljust(pad + 2)}{speaker.GRAY}{exe}{speaker.RESET}")
