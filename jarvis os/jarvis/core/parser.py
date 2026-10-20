from . import speaker

import re

# Command aliases -> canonical
ALIASES = {
    "status": ["status", "stats", "dash", "dashboard", "system"],
    "scan": ["scan", "processes", "procs", "ps"],
    "open": ["open", "launch", "run", "start"],
    "search": ["search", "find", "locate", "glob"],
    "navigate": ["cd", "navigate", "go", "chdir"],
    "list": ["list", "ls", "dir"],
    "create": ["create", "mkdir", "touch", "new"],
    "remove": ["remove", "rm", "delete", "del", "remove-item"],
    "copy": ["copy", "cp", "copy-item"],
    "move": ["move", "mv", "move-item"],
    "automate": ["automate", "schedule", "task", "cron"],
    "jobs": ["jobs", "scheduled", "list-tasks"],
    "chat": ["chat", "ask", "ai"],
    "speak": ["speak", "say", "talk", "tts"],
    "voice": ["voice", "listen", "mic", "hear"],
    "reset": ["reset", "forget", "clear-chat"],
    "skills": ["skills", "capabilities", "abilities", "features"],
    "location": ["location", "set-location", "set location", "where am i", "home"],
    "brain": ["brain", "model", "llm", "api"],
    "pc": ["pc", "pccontrol", "automate-pc", "pc control"],
    "doctor": ["doctor", "diag", "diagnostic", "health"],
    "help": ["help", "h", "?"],
    "clear": ["clear", "cls"],
    "shutdown": ["shutdown", "exit", "quit", "bye", "powerdown", "power off"],
    "authenticate": ["login", "signin", "auth", "access"],
}

COMMAND_ROWS = [
    ("status", "Show system overview (CPU, RAM, disk, battery)"),
    ("scan", "List running processes"),
    ("open <app|site>", "Launch app or open website (e.g. open youtube)"),
    ("search <pattern>", "Find files in current directory"),
    ("cd <dir>", "Change working directory"),
    ("ls", "List files in current directory"),
    ("create <name>[/]", "Create a file (or directory with trailing /)"),
    ("remove <name>", "Delete a file or directory"),
    ("copy <src> <dest>", "Copy a file"),
    ("move <src> <dest>", "Move a file"),
    ("automate <sec> <cmd>", "Schedule a recurring task"),
    ("jobs", "List scheduled tasks"),
    ("chat <message>", "Talk to Jarvis AI"),
    ("skills", "Show the Alexa-style skill list"),
    ("pc <verb>", "PC control: volume, brightness, media, screenshot, ip"),
    ("location <city>", "Set your default city (for weather)"),
    ("speak <text>", "Speak text aloud (TTS)"),
    ("voice", "Listen to the microphone and run the command"),
    ("brain", "Show LLM brain status"),
    ("doctor", "Run diagnostic checks on all providers"),
    ("login", "Authenticate with Jarvis"),
    ("shutdown", "Power down Jarvis"),
    ("help", "Show this help"),
]

# Wake-word prefixes ("hey jarvis open youtube...") are stripped so the real
# command reaches the Router/skills instead of falling through to chat/LLM.
# STT and typed input both add punctuation ("Hey, Jarvis. Open YouTube."),
# so separators after the greeting word and after "jarvis" accept
# whitespace, commas, periods, colons and semicolons.
_WAKE_RE = re.compile(r"^(?:(?:hey|hi|hello|ok|okay|yo|dear|listen)[\s,.]+)?jarvis[\s,.:;]+",
                      re.IGNORECASE)


# Multi-word aliases ("where am i", "power off") are matched as phrase
# prefixes before falling back to the single head word.
_PHRASE_ALIASES = sorted(
    ((alias.lower(), canon)
     for canon, aliases in ALIASES.items()
     for alias in aliases if " " in alias.strip()),
    key=lambda t: -len(t[0]))


def parse(text):
    cleaned = (text or "").strip()
    m = _WAKE_RE.match(cleaned)
    if m:
        rest = cleaned[m.end():].strip()
        if rest:
            cleaned = rest
    low = cleaned.lower()
    for phrase, canon in _PHRASE_ALIASES:
        if low == phrase or low.startswith(phrase + " "):
            tail = cleaned[len(phrase):].strip()
            return {"command": canon, "args": tail.split() if tail else [],
                    "raw": cleaned, "implicit": False}
    parts = cleaned.split()
    if not parts:
        return {"command": None, "args": [], "raw": "", "implicit": False}
    words_lower = [p.lower() for p in parts]
    max_words = min(len(parts), 4)
    for n in range(max_words, 0, -1):
        candidate = " ".join(words_lower[:n])
        for canonical, aliases in ALIASES.items():
            if candidate in aliases:
                return {"command": canonical, "args": parts[n:], "raw": cleaned, "implicit": False}
    return {"command": "chat", "args": parts[1:], "raw": cleaned, "implicit": True}


def help_text():
    speaker.header("COMMAND MANUAL")
    pad = max(len(r[0]) for r in COMMAND_ROWS)
    for cmd, desc in COMMAND_ROWS:
        speaker.raw(f"  {speaker.CYAN}{speaker.BOLD}{cmd.ljust(pad + 2)}{speaker.RESET}{speaker.GRAY}{desc}{speaker.RESET}")
    speaker.line("Tip: Jarvis understands natural language, just talk to me.")
