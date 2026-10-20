"""Styled terminal output (ANSI, stdlib only)."""

import os
import sys

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
GRAY = "\x1b[90m"
WHITE = "\x1b[97m"
CYAN = "\x1b[96m"
GREEN = "\x1b[92m"
RED = "\x1b[91m"
YELLOW = "\x1b[93m"

if sys.platform == "win32":
    try:
        import ctypes
        _k = ctypes.windll.kernel32.GetStdHandle(-11)
        _mode = ctypes.c_ulong()
        if ctypes.windll.kernel32.GetConsoleMode(_k, ctypes.byref(_mode)):
            ctypes.windll.kernel32.SetConsoleMode(
                _k, _mode.value | 0x0004)
    except Exception:
        pass


def raw(text=""):
    print(text, flush=True)


def line(text=""):
    print(f"{GRAY}{text}{RESET}", flush=True)


def say(text=""):
    print(f"  {WHITE}{text}{RESET}", flush=True)


def success_msg(text=""):
    print(f"  {GREEN}\u2714 {text}{RESET}", flush=True)


def error_msg(text=""):
    print(f"  {RED}\u2716 {text}{RESET}", flush=True)


def warn_msg(text=""):
    print(f"  {YELLOW}! {text}{RESET}", flush=True)


def header(text=""):
    bar = "-" * max(10, len(text) + 6)
    print(f"\n  {BOLD}{CYAN}{bar}\n  {text}\n  {bar}{RESET}", flush=True)


def clear():
    os.system("cls" if sys.platform == "win32" else "clear")
