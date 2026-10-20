# JARVIS OS

A terminal-based AI operating system assistant inspired by Iron Man's J.A.R.V.I.S.

Built with Python and the standard library. Optional extras for voice and live
metrics are all installed with one command.

## Quick Start

```bash
pip install -r requirements.txt   # optional: voice + live system metrics
python jarvis/main.py             # terminal (no login gate)
python server.py                  # web HUD at http://127.0.0.1:8000
```

If you skip the install, everything still works - voice and `psutil` features
degrade gracefully.

## Voice Control

- **Speak aloud (TTS)**: `speak <text>` or `voice on` (Jarvis then vocalizes replies)
- **Voice mode**: `voice` - listens to your microphone continuously and executes
  what you say. Say "exit" to stop. Runs on Windows (native SAPI), macOS (`say`),
  and Linux (`spd-say`/`espeak`).
- Requires `SpeechRecognition` + `pyaudio` for the microphone; TTS needs no install.
- Where mic audio goes: browser speech recognition and the server
  transcription fallback (`/api/transcribe`) both use the Google speech
  service, so audio leaves this PC in those modes. The HUD mic button
  shows the active mode (right-click to cycle AUTO / BROWSER / SERVER);
  server transcription announces itself in the feed when audio is sent.

## AI Brain (LLM)

Jarvis uses any **OpenAI-compatible** `/chat/completions` endpoint. It stays
in honest offline mode until you supply an API key or endpoint - a built-in
default URL alone is not treated as a working provider.

Use environment variables (they take precedence and keep secrets out of
`data/config.json`):

```powershell
$env:JARVIS_LLM_API_KEY = "..."
$env:JARVIS_LLM_MODEL = "gpt-4o-mini"                  # optional
# $env:JARVIS_LLM_ENDPOINT = "https://.../chat/completions"  # optional
```

Or configure individual values inside Jarvis:

```text
brain set key <api-key>
brain set endpoint http://localhost:11434/v1/chat/completions
brain set model qwen2.5:7b-instruct-q3_K_M
```

The latter two commands configure local Ollama; no API key is needed. OpenAI
uses `https://api.openai.com/v1/chat/completions` and `gpt-4o-mini` when only
an API key is provided. Check status with `brain` and clear conversation
memory with `reset`. Built-in skills execute before the LLM; the LLM is told
not to invent success for computer actions it did not verify.

## Skills (Alexa-style)

Before reaching the LLM, Jarvis checks a set of built-in **skills** that answer
and act directly - exactly how Alexa works:

| Skill | What you can say |
|-------|------------------|
| `files` | "open downloads", "open jarvis os file in desktop", "find my python files", "create a folder called X", "delete X" (asks first) |
| `opener` | "launch youtube", "play [song] on youtube", "open gmail", "open chrome", "search google for X", "chrome browser and search X", "open the first result" |
| `pc` | "volume up", "set volume to 40", "brightness down", "next track", "take a screenshot", "copy X to clipboard", "notify me X", "what's my IP", "close notepad", "lock the computer", "click", "press enter" |
| `weather` | "what's the weather in Tokyo?", "temperature in Paris" |
| `wikipedia` | "who is Marie Curie?", "what is thermodynamics" |
| `websearch` | "search the web for X", "look up X" |
| `maths` | "what is 2 + 2", "15% of 200", "convert 10 miles to km" |
| `timers` | "set a 5 minute timer", "show timers", "cancel the timer" |
| `notes` | "remember my wifi password is X", "what do you remember" |
| `system` | "how much memory is free", "battery", "disk space" |

- Weather uses **Open-Meteo** (free, no key). Set your home city: `location <city>`
- Web/knowledge use DuckDuckGo + Wikipedia (free, no key)
- Everything works offline except weather/websearch/wikipedia (those need internet)

Type `skills` to see the list inside Jarvis.

### PC control (Windows hands - ported from PC-Automation)

The `pc` command (alias `pccontrol`, `automate-pc`) gives Jarvis verified hands on
Windows, rebuilt from the [PC-Automation](https://github.com/AnubhavChaturvedi-GitHub/PC-Automation)
repo: the agent is the intent brain, this is only the hands. Stdlib-only backend
(PowerShell P/Invoke + ctypes; `pyaudio`/`psutil` optional). It never steals the
REPL and never exits the shell.

- `pc doctor` - capability audit (run first in a new environment)
- `pc <family> <action> --dry-run` - print what a keystroke/URL verb would do
- System: `pc battery`, `pc volume get|set N|up|down|mute|unmute`,
  `pc brightness get|set N|up|down`, `pc ip [--public]`, `pc apps`, `pc app open|quit|restart|running|front`
- Web/YouTube: `pc web NAME_OR_URL` (URL > 186-site cache > reachability guess > search),
  `pc youtube play|search QUERY`
- Keystrokes (sent to the frontmost app): `pc browser <20 actions>`,
  `pc yt <22 actions>`, `pc media status|play-pause|next|prev`,
  `pc keys COMBO`, `pc type TEXT`
- Mouse: `pc mouse move X Y|click|double-click|right-click|scroll N`
- Desktop: `pc screenshot`, `pc clipboard get|set TEXT`, `pc notify MSG`, `pc say TEXT`
- Power: `pc lock|sleep|shutdown|restart|settings|taskmanager|terminal|explorer [path]`
- Hardware: `pc mic-test`, `pc speaker-test [--measure]`
- Every verb accepts `--json`; volume and clipboard are saved/restored by the gate

`scripts/gate.py` is a measured PC-control gate with negative tests,
regression locks, and an optional `--live` Notepad keystroke round trip.
Volume and clipboard are saved and restored. Run the non-audible safe pass
with `python scripts/gate.py --quiet`; its final `NOT COVERED` list is the
truthful record of capability boundaries on that machine.

### App discovery + verified actions

`jarvis/modules/apps.py` locates applications (PATH, App Paths registry, known
install dirs, Start Menu) and every launch/close is verified against running
processes. Missing apps get an honest "I couldn't find X installed" - never a
fake success. Protected system processes (explorer, dwm, ...) can't be killed.

Wake words ("hey jarvis ...") are stripped before parsing, so voice-style
commands work typed or spoken. Recent result URLs and the last-used browser
are remembered: "open chrome and search for python", then "open the first
result".

### Safety model

- Safe actions (open, search, screenshots, volume, mouse, typing) run at once.
- Destructive actions ask first, showing the resolved target: `delete` /
  `remove` files, `shut down` / `restart` / `sleep` the computer. Say `yes`
  to confirm, `no` to cancel (expires in 2 minutes).
- Delete/create refuse case-variant surprises (`Jarvis` vs `jarvis` are the
  same file on Windows) and anything outside the working folder.
- Explicitly typed `pc shutdown`-style commands execute immediately: typing
  it is the confirmation.

### Web HUD

```bash
python server.py            # HUD + API on http://127.0.0.1:8000
python server.py --port 8080
```

Open the HUD through the server address above. Do NOT double-click
`frontend/index.html` as a file: browsers block the microphone, `fetch()`
and saved permissions on `file://` pages, so every panel stays in demo mode.
The served HUD warns you if it detects that launch.

The HUD pipes through the exact same Router and skills as the terminal, so
every command above works in the browser too (spoken replies use the
browser mic/speaker). The bridge only listens on 127.0.0.1 and has no
password gate; POST endpoints additionally reject non-loopback
Host/Origin (see Authentication). The HUD never claims an action ran
unless the backend confirms it: if the server is unreachable, commands
report "nothing was executed" and telemetry shows OFFLINE.

## Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `status` | `dash` | System overview (CPU, RAM, disk, battery) |
| `scan` | `ps` | List running processes |
| `open <app>` | `launch` | Launch an application or open a website |
| `pc <verb>` | `pccontrol` | PC control: `pc doctor`, `volume`, `brightness`, `media`, `screenshot`, `ip` |
| `search <pattern>` | `find` | Find files recursively (regex supported) |
| `cd <dir>` | `go` | Change working directory |
| `ls` | `dir` | List files in current directory |
| `create <name>[/]` | `touch` | Create file (or directory with trailing `/`) |
| `remove <name>` | `rm` | Delete a file or directory |
| `copy <src> <dest>` | `cp` | Copy a file |
| `move <src> <dest>` | `mv` | Move a file |
| `automate <sec> <cmd>` | `schedule` | Schedule a recurring task |
| `jobs` | `list-tasks` | List scheduled tasks |
| `chat <message>` | `ask` | Talk to Jarvis AI |
| `skills` | `capabilities` | Show the skill list |
| `location <city>` | - | Set your home city (weather) |
| `speak <text>` | `say` | Speak text aloud (TTS) |
| `voice [on\|off]` | `listen` | Mic voice mode / toggle spoken replies |
| `brain` | `llm` | Show/set the LLM brain |
| `reset` | `forget` | Clear chat memory |
| `login` | `auth` | Authenticate with Jarvis |
| `clear` | `cls` | Clear the screen |
| `shutdown` | `exit` | Power down Jarvis |
| `help` | `?` | Show the command manual |

Any unrecognized input is treated as a chat message - just talk naturally.

## Architecture

```
jarvis/
├── main.py             Entry point & REPL
├── core/
│   ├── parser.py       Command parsing & aliases
│   ├── speaker.py      Styled terminal output
│   ├── auth.py         Security & authentication
│   └── voice.py        Text-to-speech & speech-to-text
├── modules/
│   ├── system.py       CPU, RAM, disk, process monitoring
│   ├── files.py        File system manager (exact-case + cwd guards)
│   ├── apps.py         App discovery + verified launch/close
│   ├── pccontrol.py    Windows verb catalog (volume, keys, mouse, power...)
│   ├── scheduler.py    Task automation (threaded scheduler)
│   ├── launcher.py     Application launcher (legacy fallback)
│   ├── chat.py         Conversational brain (local + LLM)
│   └── llm.py          OpenAI-compatible API client (std-lib only)
├── skills/           Alexa-style intent skills (files, opener, pc, ...)
└── utils/
    └── storage.py      JSON file-based persistence (data/)
```

## Authentication

There is no password gate: the terminal opens straight into the REPL and
the web HUD answers without login. The bridge only listens on 127.0.0.1,
and state-changing API calls (POST) additionally require a loopback
`Host` and, when present, a loopback `Origin`, which blocks
DNS-rebinding and cross-origin pages from driving it. Reads
(status/telemetry/static files) stay public on loopback. The `login`
command and `jarvis/core/auth.py` remain for compatibility but gate
nothing. Destructive actions still ask first (see Safety model).

## Verification

```bash
python -m unittest discover -s tests -v   # isolated, no hardware actions
python scripts/gate.py --quiet            # hardware/control capability gate
python server.py                           # HUD at http://127.0.0.1:8000
```

The regression tests never launch apps, inject keystrokes, or contact an LLM.

## Extending

- **Plugins**: Add new modules under `modules/` and wire them in `main.py`
- **Voice engine**: Swap `core/voice.py` for Whisper, Azure, etc.
- **LLM**: Any OpenAI-compatible provider, or fork `modules/llm.py`

## Documentation

- `docs/PROJECT_GUIDE.md` - complete project explanation (languages,
  architecture, how every part works, demo script, Q&A).
- `docs/REFERENCES.md` - five verified reference papers with citations,
  BibTeX and report-ready usage notes.
- `docs/JARVIS_ROADMAP.md` - architecture review and phased plan.

## License

MIT