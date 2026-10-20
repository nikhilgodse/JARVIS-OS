# JARVIS OS - Complete Project Guide

Last updated: 2026-10-18

This document explains the entire JARVIS OS project in plain language: what
it is, which programming languages are used and why, how every part works,
how to run it, how it is tested, and how to present it to a project guide.
It is written so that someone who has never seen the code can understand the
whole system after reading it.

---

## 1. What JARVIS OS is

JARVIS OS is a personal assistant for Windows. It listens through a
microphone or reads typed commands, understands natural language, and
actually performs tasks on the computer. It is not a chatbot that only
talks: it opens apps and websites, plays YouTube videos, controls volume
and brightness, takes screenshots, manages files, sets timers, remembers
notes, reports weather and system status, sends WhatsApp messages, and
holds normal conversations using a local AI model.

Key facts at a glance:

- It has two front ends: a terminal (command line) and a browser HUD
  (futuristic dashboard page). Both share the same brain.
- The backend is written with the Python standard library only. No web
  framework, no database server, no build tools.
- The AI brain runs locally on the machine through Ollama with an
  open-weight model (Qwen2.5 7B). Cloud AI (NVIDIA) is optional and off
  by default.
- Most features work offline. Only voice recognition, web search,
  weather and Wikipedia need internet.
- The project contains 11 skills, 23 terminal commands, 8 HTTP API
  routes, and 148 automated tests.

The name comes from Iron Man's assistant; the project is inspired by the
useful experiences of assistants like Alexa, Siri and Gemini, but it does
not claim to match them and does not copy their branding.

---

## 2. Languages used, and what each one does

| Language | Where it is used | Files / size | Why this language |
|----------|------------------|--------------|-------------------|
| Python 3.13 | The entire backend: assistant core, skills, LLM client, web server, tests, hardware check script | 53 files, about 7,200 lines | Best support for Windows automation (processes, registry, files), huge standard library, fast to develop and easy to test |
| JavaScript | Browser HUD logic: voice recognition, wake word, chat rendering, live telemetry updates | frontend/app.js, 1,239 lines | Browsers run it natively; it has direct access to the microphone and speech APIs, no installation needed |
| HTML5 | Structure of the HUD page (panels, buttons, feed) | frontend/index.html, 184 lines | Standard markup for the web interface |
| CSS3 | Visual design of the HUD: dark futuristic theme, reactor animation, responsive layout | frontend/styles.css, 222 lines | Standard styling language of the web |
| JSON | Data storage and the website database | data/*.json (runtime), jarvis/assets/websites.json (187 sites) | Simple, human-readable, no database engine required |
| Windows Batch | Double-click launcher for the whole system | start-jarvis.bat on Desktop | Standard Windows way to launch the server without typing commands |
| Markdown | Documentation | README.md, docs/JARVIS_ROADMAP.md, this guide | Readable text documents that render nicely on GitHub and in editors |

Total source code: about 8,850 lines across Python, JavaScript, HTML and CSS.

Technologies deliberately NOT used (and why):

- No web framework (no Flask/Django). Python's built-in `http.server` is
  enough for a local single-user bridge, and it keeps the project
  dependency-free.
- No database (no MySQL/SQLite schema). Notes, timers, config and
  scheduled jobs are small JSON files. The data is easy to inspect,
  back up and delete.
- No JavaScript framework (no React/Vue). The HUD is one page with plain
  JavaScript, so there is no build step: edit a file, refresh the page.
- No cloud requirement. The AI model runs on the same computer. The
  optional NVIDIA cloud provider exists as a fallback but is disabled
  unless a key is configured.

Python packages used (all optional, all installed with one command):

- `psutil` - read real CPU, RAM, disk and battery numbers.
- `pyttsx3` - text-to-speech in the terminal (falls back to built-in
  Windows SAPI voice if missing).
- `SpeechRecognition` + `pyaudio` - microphone capture for the terminal
  voice mode and the server transcription fallback.
- `pywhatkit` - WhatsApp automation.
- `requests` - weather/API calls.

If these are missing, the project still runs and degrades gracefully.

---

## 3. How the project works - the big picture

Two front doors, one shared brain:

```
                        +----------------------+
                        |     YOU (voice/text) |
                        +----------+-----------+
                                   |
             +---------------------+---------------------+
             |                                           |
             v                                           v
   Terminal REPL                             Browser HUD (frontend/)
   (jarvis/main.py)                          dashboard + mic + speaker
             |                                           |
             |                                  server.py (HTTP bridge
             |                                  on 127.0.0.1:8000)
             |                                           |
             +---------------------+---------------------+
                                   v
                    Router.run()   (jarvis/main.py)
                                   |
               parser.parse()  (jarvis/core/parser.py)
               - strips wake word "Hey Jarvis"
               - maps aliases ("launch" -> "open", "rm" -> "remove")
                                   |
               +-------------------+-------------------+
               |                                       |
               v                                       v
      WhatsApp intent check                  Skill dispatcher
      (high-confidence messages             (jarvis/skills/__init__.py)
       route straight to skill)                        |
                                                       v
                          local replies -> 11 skills -> LLM brain
                          (chat.py)                     |
                                       +----------------+----------------+
                                       |                                 |
                                       v                                 v
                              Ollama local model               NVIDIA NIM (cloud)
                              qwen2.5:7b, offline              optional, needs API key
                                       |
                                       v
                          Actions on the real machine:
                          apps, files, volume, brightness, media,
                          clipboard, screenshots, timers, notes,
                          WhatsApp, scheduler, system sensors
```

The important design rule: command parsing, conversation, skill
execution and persistence are separate layers. A voice command and a
typed command travel the exact same path, so behavior is consistent
everywhere.

---

## 4. The journey of one command (voice example)

Say: "Hey, Jarvis. Open notepad please."

1. **Capture.** The HUD mic is in STANDBY mode listening for the wake
   word. Chrome's Web Speech API turns your speech into text
   ("Hey, Jarvis. Open notepad please."). If browser recognition is
   unavailable, the HUD records a WAV file and posts it to the server,
   which transcribes it. Both paths use the Google speech service, and
   the HUD tells you when audio is sent (privacy disclosure).
2. **Wake word check.** The HUD's wake regex accepts "Hey Jarvis" with
   any punctuation ("hey, jarvis.", "hey jarvis:", etc.). Everything
   after the wake word is the actual command.
3. **Transport.** The HUD sends `POST /api/run` with the raw text to the
   local server. The server first checks the request came from loopback
   (Host/Origin check - this blocks malicious web pages and DNS
   rebinding attacks).
4. **Routing.** The server calls `Router.run(text)`. The router checks
   WhatsApp intent first (so "message Rahul on whatsapp" never gets
   misrouted to a web search), then runs the parser.
5. **Parsing.** `parser.parse()` strips the wake word again (so the
   terminal path works too), and maps the first word(s) through the
   alias table: "open" is a command, "notepad please" is the argument.
6. **Skill execution.** For `open`, the router tries, in order: open a
   folder, open a local file, open a known website, or launch an
   installed application. The app resolver checks an alias map, PATH,
   the Windows "App Paths" registry, common install folders, and Start
   Menu shortcuts - then launches the app and verifies with psutil that
   the process actually started. A missing app answers honestly:
   "I couldn't find X installed" - never a fake success.
7. **Reply.** The result text goes back to the server, which returns it
   as JSON. The HUD prints it in the chat feed and speaks it aloud if
   voice replies are on.

A typed command skips steps 1-2 and enters at step 3 from the HUD, or
goes straight into `Router.run()` in the terminal.

**What happens for plain conversation?** If no command or skill matches,
the text reaches `ChatBrain` (jarvis/modules/chat.py). It first tries
deterministic local replies (greetings, time, date, identity), then the
skills again, and only then the LLM. This ordering keeps replies instant
and consistent: "who are you" always answers the same way instead of
hitting Wikipedia or the model.

---

## 5. Folder map - what everything is

```
jarvis os/
|-- jarvis/                  THE ASSISTANT (Python package)
|   |-- main.py              Router: runs every command, terminal REPL entry
|   |-- core/
|   |   |-- parser.py        Command aliases + wake-word stripping + help table
|   |   |-- speaker.py       Colored terminal output helpers
|   |   |-- voice.py         Text-to-speech + one-shot mic capture (terminal)
|   |   |-- auth.py          Compatibility login (salted PBKDF2 hash)
|   |-- modules/             ENGINE ROOM (not conversational)
|   |   |-- chat.py          Conversation brain: local -> skills -> LLM
|   |   |-- llm.py           LLM provider router (Ollama local, NVIDIA cloud)
|   |   |-- pccontrol.py     Windows hands: volume, brightness, media, typing,
|   |   |                    clipboard, screenshots (largest module, 1,062 lines)
|   |   |-- apps.py          App discovery + verified launch/close
|   |   |-- system.py        Real system sensors (CPU, RAM, disk, battery)
|   |   |-- scheduler.py     Recurring tasks, persisted across restarts
|   |   |-- files.py         File manager (safe cwd-scoped operations)
|   |   |-- launcher.py      Small known-app launcher + list
|   |-- skills/              WHAT JARVIS UNDERSTANDS (one file per skill)
|   |   |-- __init__.py      Skill registry + system-summary skill
|   |   |-- whatsapp.py      WhatsApp messaging with preview + confirm
|   |   |-- files.py         find/open/create/delete files
|   |   |-- opener.py        Open websites/apps, YouTube, play music
|   |   |-- pc.py            Voice layer for PC control (volume etc.)
|   |   |-- maths.py         Calculations + unit conversion
|   |   |-- notes.py         Remember/recall notes
|   |   |-- timers.py        Timers and alarms
|   |   |-- weather.py       Weather via Open-Meteo (no API key needed)
|   |   |-- websearch.py     DuckDuckGo instant answers
|   |   |-- wikipedia.py     General knowledge lookup
|   |   |-- confirm.py       Confirmation flow for destructive actions
|   |   |-- phrases.py       Shared "polite wrapper" stripping ("please...")
|   |-- utils/
|   |   |-- storage.py       Atomic JSON load/save under data/
|   |-- assets/
|       |-- websites.json    187 known sites ("open youtube" -> URL)
|-- frontend/                THE HUD (browser interface)
|   |-- index.html           Page structure
|   |-- styles.css           Visual design
|   |-- app.js               All HUD logic: voice, wake word, chat, telemetry
|-- server.py                HTTP bridge: serves the HUD + /api/* endpoints
|-- tests/                   148 automated tests (20 files)
|-- scripts/gate.py          Hardware capability check (45 checks)
|-- data/                    Runtime data (JSON): config, notes, timers,
|                            jobs, results, pending confirmations
|-- docs/
|   |-- JARVIS_ROADMAP.md    Architecture review + phased improvement plan
|   |-- PROJECT_GUIDE.md     This document
|-- README.md                Setup + full command reference
|-- requirements.txt         Optional Python packages
|-- .env / .env.example      Provider configuration (keys, endpoints, model)
```

---

## 6. Components in detail

### 6.1 Terminal application (jarvis/main.py)

The terminal REPL is the original interface. `Router.run(text)` is the
single entry point used by the terminal AND the web server. It supports
23 commands (status, scan, open, search, cd, ls, create, remove, copy,
move, automate, jobs, chat, skills, pc, location, speak, voice, brain,
reset, login, clear, shutdown) plus natural language through the chat
brain. Aliases are mapped in `core/parser.py` ("launch" -> open, "rm" ->
remove, "ps" -> scan, etc.).

### 6.2 The parser (jarvis/core/parser.py)

Two jobs:

1. **Wake-word stripping.** "Hey Jarvis, open YouTube" must not fall
   through to the LLM as a chat sentence. The regex accepts hey/hi/ok/yo
   before "jarvis" and any punctuation after it (commas, periods,
   colons), because speech-to-text output contains punctuation.
2. **Alias mapping.** First-word (up to 4 words, longest match first)
   lookup in the alias table, then the rest becomes arguments. Multi-word
   aliases like "where am i" and "power off" are handled as phrases.

Anything that matches nothing becomes a `chat` command and reaches the
conversation brain.

### 6.3 The 11 skills

| Skill | What it does | Example commands |
|-------|--------------|------------------|
| whatsapp | Sends WhatsApp messages; shows a preview first, needs "yes" | "message rahul on whatsapp saying I'll call later" |
| files | Find, open, create, delete files and folders; delete asks first | "find report.pdf", "create notes.txt", "delete old.txt" |
| opener | Opens websites (187-site database), YouTube, plays music | "open youtube", "play despacito", "open google" |
| pc | PC control by voice: volume, brightness, media, screenshots, clipboard | "set volume to 30", "pause the music", "read the clipboard" |
| system | Live system status summaries | "how is my system", "battery status", "cpu usage" |
| maths | Calculations and unit conversions | "calculate 15% of 240", "convert 5 km to miles" |
| notes | Remember and recall short notes | "remember my project demo is Friday", "what did I ask you to remember" |
| timers | Timers and reminders that speak when done | "set a timer for 10 minutes", "remind me in 5 minutes" |
| weather | Weather for any city via Open-Meteo (free, no key) | "what's the weather in Delhi" |
| websearch | Web answers via DuckDuckGo | "search for the latest AI news" |
| wikipedia | People, places, general knowledge | "who is Ada Lovelace" |

Skills run in a fixed priority order (top of the list wins on overlap).
Each skill is a plain function `handler(text, ctx)` that returns a reply
string or None. Adding a skill means writing one file and registering a
line in `jarvis/skills/__init__.py`.

Every skill strips polite wrappers ("please open notepad", "open notepad
please") through the shared `skills/phrases.py`, so natural speech works.
There is a deliberate exception: PC keystroke injection ("type ..." /
"press ...") matches the original text, because stripping words could
change what gets typed into another application.

### 6.4 The conversation brain (jarvis/modules/chat.py)

Three-tier routing, in order:

1. **Local deterministic replies** - greetings ("What do you need."),
   thanks ("Yeah, no problem."), identity, time, date, current folder.
   Instant, no model needed, consistent on every turn.
2. **Skills** - any matching skill answers instead of the model.
3. **LLM** - everything else goes to the configured model with a bounded
   12-turn conversation history.

The persona is deliberately terse and informal (the owner asked for a
"nonchalant, speak only what's needed" style). A greeting that introduces
a real command ("hey play despacito") is detected and routed to skills
instead of being answered with a greeting.

### 6.5 The AI brain (jarvis/modules/llm.py)

The module is a small provider router:

- **Ollama (local, primary).** Endpoint `http://127.0.0.1:11434`, model
  `qwen2.5:7b-instruct-q3_K_M`. This model was chosen by measurement:
  the Q4 version needed 5.2 GB of VRAM but the machine has 6 GB, so 18%
  spilled to CPU and answers took 11-20 seconds. The Q3 version fits
  100% on the GPU (about 3.9 GB), answers at about 37 tokens per second,
  and loads in about 7 seconds. The superseded Q4 model was deleted;
  `llama3.2:3b` remains as a small fallback.
- **NVIDIA NIM (cloud, optional).** Only used if an API key is set, and
  automatic failover is off by default so nothing is sent to the cloud
  silently.

Health reporting is honest and three-layered: a provider is
`is_configured()` (has enough config to try), `server_reachable` (the
endpoint answered) and `model_available` (the model exists). The status
is `online`, `degraded` or `offline` based on measurements, never on the
mere presence of a URL. The HUD status bar reads these measured fields.

A subtle fix worth mentioning: Ollama binds IPv4 only, but on Windows
`localhost` resolves to IPv6 first, which added about 2 seconds to every
request. The code connects to `127.0.0.1` while still reporting the
configured endpoint unchanged.

### 6.6 PC control (jarvis/modules/pccontrol.py)

The "hands" of the system, 1,062 lines. Everything is done through
Windows APIs and standard tools: volume and media keys through key
events, brightness through WMI, screenshots through .NET PowerShell,
clipboard through the Win32 clipboard, typing/keystrokes through
SendInput-style key events. The voice-facing layer in `skills/pc.py`
handles phrases like "volume up", "mute", "pause the music", "take a
screenshot", "read the clipboard". Every action has a dry-run mode used
by the gate script to verify capability without side effects.

### 6.7 App discovery and verified launch (jarvis/modules/apps.py)

Resolving "open chrome" to a real program is harder than it sounds.
Resolution order: alias map -> PATH (real .exe preferred over .cmd
shims) -> Windows "App Paths" registry -> known install directories ->
Start Menu shortcut scan. After launching, the module polls psutil for a
matching process. Only then does it report success. Closing apps has the
same verification and a protected-process list (explorer, dwm, etc. are
never killed).

### 6.8 System monitor (jarvis/modules/system.py)

Real data through psutil: CPU load, RAM used/total, disk usage, battery
percentage and charge state, uptime. No fake numbers anywhere. The HUD
labels core temperature as EST (estimated from CPU load), because
Windows exposes no temperature sensor through the standard library.

### 6.9 Scheduler (jarvis/modules/scheduler.py)

"automate 60 <command>" creates a recurring task on a background thread.
Jobs are persisted to `data/jobs.json` and resumed on restart; cancelled
jobs are removed from disk so they cannot come back. One task =
one thread with a stop event, which is simple and safe for the small
number of jobs this assistant handles.

### 6.10 File safety (jarvis/modules/files.py + skills/files.py)

All file commands are scoped to a working folder. The manager refuses
path escapes, refuses case-variant surprises ("Jarvis" vs "jarvis" are
the same file on Windows) and routes destructive actions through the
confirmation flow.

### 6.11 The web server (server.py)

A `ThreadingHTTPServer` on `127.0.0.1:8000` using only the standard
library. It serves the HUD static files and 8 API routes:

| Route | Method | Purpose | Access |
|-------|--------|---------|--------|
| /api/status | GET | Overall state: snapshot, auth, LLM, providers | Public (read) |
| /api/providers | GET | Provider list + measured health | Public (read) |
| /api/telemetry | GET | CPU/RAM/disk/uptime for the HUD gauges | Public (read) |
| /api/weather | GET | Weather proxy for the HUD | Public (read) |
| /api/logs | GET | Recent log lines | Public (read) |
| /api/run | POST | Run any assistant command | Loopback only |
| /api/login | POST | Compatibility login (gates nothing) | Loopback only |
| /api/transcribe | POST | Speech-to-text for the WAV fallback | Loopback only |

Security model: the socket binds to loopback only, and every POST must
come with a loopback Host and (when present) a loopback Origin. That
blocks DNS-rebinding and malicious web pages from driving the machine.
Request bodies are capped at 256 KB. This was added deliberately: a
browser page visited by a local process could otherwise POST commands.

### 6.12 The HUD (frontend/)

A single-page dashboard: chat feed, reactor animation, live gauges,
weather panel, mic button, transcript panel, clock. No framework, no
build step. It polls `/api/status` and `/api/telemetry` and paints real
numbers only: if the backend is down, gauges show "--" and OFFLINE, and
commands answer "Backend unreachable - nothing was executed." This
honesty rule was a specific design decision: earlier versions showed
invented "all systems online" messages and random telemetry, which can
mislead a user into thinking an action ran when it did not.

### 6.13 Voice pipeline

Two recognition paths (the HUD mic button shows the active mode; right
click cycles AUTO / BROWSER / SERVER):

- **Browser**: Chrome/Edge Web Speech API. Fast, real-time.
- **Server fallback**: the HUD records a 16 kHz WAV and posts it to
  `/api/transcribe`; the server runs SpeechRecognition's Google backend.

Both paths use the Google speech service, and the HUD discloses this
when audio is sent. Reply speech uses the browser speech synthesizer;
the terminal uses Windows SAPI (no install required) or pyttsx3 if
available.

**Assist modes** (the ASSIST button cycles):

- OFF - push to talk (click the mic for one command).
- TALK - hands-free conversation: it keeps listening and auto re-listens
  after each command, including a short "wait for me" mode when it hears
  you thinking. Say "goodbye" / "stop" / "that's all" to end.
- STANDBY - always-on wake word: the mic stays open waiting for
  "Hey Jarvis"; only an utterance containing the wake word becomes a
  command. The wake regex tolerates all punctuation.

Timers: if a timer fires while you are away, JARVIS speaks the reminder
through the browser.

### 6.14 Data storage (jarvis/utils/storage.py)

All state is small JSON files in `data/`, written atomically (write to a
temp file, then rename - so a crash cannot corrupt a file):

| File | Contents |
|------|----------|
| config.json | City, voice setting, provider/LLM config, auth hash |
| notes.json | Everything you told it to remember |
| timers.json | Pending timers (so they survive restarts) |
| jobs.json | Scheduled recurring tasks |
| pending_confirm.json | A destructive action waiting for "yes"/"no" (expires in 2 minutes) |
| results.json | Last command results |

Deleting a file clears that category of data; there is no hidden
database anywhere.

### 6.15 Safety model

- Destructive actions (delete/remove files, shutdown, restart, sleep)
  ask for confirmation showing the resolved target, and expire after
  2 minutes. Answer "yes" or "no".
- Explicitly typed PC commands ("pc shutdown") execute immediately -
  typing it is the confirmation.
- App launch/close is verified through process polling; failure is
  reported honestly.
- The LLM never executes shell commands or bypasses these rules: the
  model can only talk, and its instructions to the system are only the
  same skill phrases a human could type.
- The web bridge rejects non-loopback POSTs (see 6.11).
- Unknown/unmatched commands never pretend to run.

---

## 7. Testing and verification

Everything below was actually executed on this machine; the numbers are
real, not targets.

**Automated test suite: 148 tests, all passing** (`python -m unittest
discover -s tests`). The tests never launch apps, inject keystrokes or
contact an LLM - external effects are stubbed. Highlights:

| Test file | Covers |
|-----------|--------|
| test_parser.py | Aliases, wake-word stripping with punctuation |
| test_voice.py, test_voice_allskills.py | Every skill reachable by voice phrasing, "please" wrappers |
| test_opener_voice.py, test_opener_offline.py | YouTube/play routing, offline website behavior |
| test_bridge_safety.py | Live server tests: loopback Host/Origin gate, 403/413 responses |
| test_frontend_honesty.py | Tripwire: no fake success strings can leak back into the HUD |
| test_llm.py | Provider router, config resolution, health model |
| test_scheduler.py | Job persistence, resume, cancel |
| test_whatsapp*.py, test_files_guards.py, test_confirm.py, test_timers.py, test_notes.py, test_weather.py, test_maths.py, test_server.py | Skill behavior and guards |

**Hardware capability gate: 45 checks passed, 0 failed, 1 skipped**
(`python scripts/gate.py`). This drives the real Windows APIs in dry-run
mode: volume, brightness, media keys, clipboard, screenshots, app
resolution. The one skipped check depends on attached hardware.

**Environment health:** `pip check` reports no broken requirements;
Python 3.13.15; model verified running 100% on GPU at about 37 tokens
per second.

**Manual end-to-end verification:** spoken and typed commands were run
through the live server on this machine (open apps, YouTube playback,
timers, notes, volume, clipboard, system status), and the code was
adjusted until each path worked. The test batteries are rerunnable
scripts kept in the project's temp workspace.

---

## 8. How to run the project

First time:

```powershell
# 1. Install the optional voice + metrics packages (needed once)
C:\Users\nikhi\AppData\Local\Programs\Python\Python313\python.exe -m pip install -r requirements.txt

# 2. Make sure Ollama is running (its tray app auto-starts it)
#    and the model exists:
C:\Users\nikhi\AppData\Local\Programs\Ollama\ollama.exe list
#    should show: qwen2.5:7b-instruct-q3_K_M
```

Every time:

- **Double-click `start-jarvis.bat` on the Desktop**, or run
  `python server.py`, then open `http://127.0.0.1:8000` (use this
  address, not `localhost` - Ollama and the mic permissions behave
  better on 127.0.0.1).
- Terminal-only mode: `python jarvis/main.py`.
- The first time you use the mic, allow microphone access in the browser
  prompt; then click the mic button, or switch ASSIST to STANDBY for
  hands-free "Hey Jarvis" mode.
- The server prints `JARVIS bridge online: http://127.0.0.1:8000` when
  it is ready.

---

## 9. Demo script for the project guide (about 7 minutes)

Prepare: Ollama running, server started, HUD open at 127.0.0.1:8000,
browser zoom at 100%, volume audible.

1. **Boot (30 s).** Show the HUD. Point out the honest status line:
   hostname, platform, LLM `CONNECTED (qwen2.5...)` from measured
   health, provider name. The feed says "HUD loaded. Probing backend..."
   then the real verdict - no fake "all systems online" theater.
2. **Typed commands (1 min).** In the input box:
   - `system status` -> the gauges are real psutil readings.
   - `calculate 15% of 240` -> instant math skill.
   - `remember my project demo is Friday` then `what did I ask you to
     remember` -> notes skill.
3. **Voice, push-to-talk (1 min).** Click the mic; say "Hey Jarvis, open
   notepad". Notepad opens; the feed shows what was heard and the
   honest result. Close Notepad.
4. **Hands-free wake word (1 min).** Click ASSIST until STANDBY. Say:
   "Hey Jarvis, how is my system" (it answers with real numbers), then
   "Hey Jarvis, open YouTube" (the site opens). Say "goodbye" to end the
   session, or click ASSIST back to OFF.
5. **Safety demonstration (1 min).** Type `delete demo.txt` (create the
   file first with `create demo.txt`) -> it asks for confirmation with
   the resolved path -> answer `no`. Then show that `pc volume 20` just
   runs because typing it is the confirmation.
6. **AI conversation (1 min).** Ask a general question requiring the
   model, e.g. "explain what a REST API is in two sentences". Point out
   the model is running locally on the GPU (Ollama) - no cloud bill, no
   data leaving the machine for this.
7. **Proof of quality (1 min).** In a terminal run
   `python -m unittest discover -s tests` -> 148 tests OK in about 8
   seconds. Then `python scripts/gate.py --quiet` -> 45 passed, 1
   skipped. Mention tests never touch the real machine (stubbed), and
   the gate is the hardware capability check.

If asked about the roadmap or future phases, open
`docs/JARVIS_ROADMAP.md` - it is the architecture review with the
phased plan.

---

## 10. Likely questions from the guide, with short answers

**Q: Why did you choose Python?**
A: The assistant must drive Windows itself: processes, registry, files,
keystrokes. Python has the best ecosystem for that (psutil, winreg) plus
a standard-library web server, so the whole backend needs no framework
at all.

**Q: Why is there a JavaScript part?**
A: Browsers are the only place with free, built-in, real-time speech
recognition and speech synthesis. The HUD uses the Web Speech API
directly, which is why voice input works with zero extra software on the
client side.

**Q: Is the AI model yours? Did you train it?**
A: No, and we do not claim it. The project uses an open-weight model
(Qwen2.5 7B) running locally through Ollama. The project's own work is
the orchestration around it: command understanding, skills, safety,
state, and the honest reporting layer.

**Q: Is this as good as Alexa, Siri or Gemini?**
A: No, and the project does not claim parity. It is measurably good at
its owner's tasks: Windows automation, local privacy, no subscription,
and full transparency because the whole stack is visible and testable.

**Q: How does voice recognition work here?**
A: The HUD uses the browser's speech recognition (Google service) for
real-time input, with a server-side fallback that transcribes recorded
WAV audio. The code states clearly when audio is sent to the speech
service.

**Q: Does it work without internet?**
A: Mostly yes. Typed commands, all skills, the local LLM, timers, notes
and TTS work offline. Voice recognition (the browser API), weather, web
search and Wikipedia need internet. The assistant degrades honestly:
it says what is unavailable instead of inventing results.

**Q: How do you stop it from doing something dangerous by accident?**
A: Three layers: destructive actions require an explicit confirmation
with the resolved target; the LLM can never execute shell code directly
(it only produces words, which pass the same guards as typed text); and
the web bridge only accepts loopback requests with loopback
Host/Origin, so no malicious page can drive the machine.

**Q: How do you know an action actually happened?**
A: The code only reports what it can verify. App launches are confirmed
by polling for the process; file operations report their real result;
system numbers come from psutil. Every failure path answers with an
honest error, and a test file (test_frontend_honesty.py) fails the
build if any fake success message ever finds its way back into the HUD.

**Q: What is the biggest technical challenge you solved?**
A: Two examples: (1) Routing - natural speech overlaps between skills
("open" a file vs a site vs an app; WhatsApp vs web search), solved
with priority routing, intent detection and 100+ regression tests for
voice phrasing. (2) Model size vs hardware - the 7B model at Q4 quality
overflowed the 6 GB GPU and answered in 11-20 s; switching to Q3 fit
100% on the GPU and brought replies to about 37 tokens/s, verified by
benchmarking.

**Q: How is data stored? Any privacy issues?**
A: Everything is local JSON under data/ (notes, timers, config). There
is no database and no telemetry. Audio leaves the machine only during
speech recognition, to the Google speech service, and the UI discloses
it. The LLM runs locally, so conversations never leave the machine.

**Q: How do you test a project that controls a real computer?**
A: 148 unit tests cover routing, parsing, safety guards and provider
logic with all hardware effects stubbed - they never press keys or open
apps. A separate gate script drives the real Windows APIs in dry-run
mode to prove capability. This split means tests are safe to run while
you work, and the gate tells you what this specific machine can do.

**Q: What would you build next?**
A: The roadmap phases: per-session memory isolation, streaming
(typing-out-loud) replies, pluggable STT/TTS providers with explicit
privacy choices, more tools with declared permissions, and a measured
quality evaluation set. See docs/JARVIS_ROADMAP.md.

---

## 11. Honest limitations (what it cannot do yet)

- Core temperature is estimated from CPU load (Windows exposes no
  temperature sensor through the standard library), and it is labeled
  EST in the HUD.
- Browser tabs share one assistant session; per-session isolation is on
  the roadmap, not done.
- Replies are not streamed token-by-token yet; the HUD waits for the
  full reply.
- No image or camera understanding.
- No remote access by design: the server binds to loopback only.
- The wake-word standby mode needs internet speech recognition; an
  offline wake engine is a future option.
- The JavaScript HUD has no unit-test harness yet; its logic is covered
  by tripwire tests and review (roadmap phase 5).

---

## 12. Glossary (plain-language)

- **LLM** - Large Language Model, the AI that writes conversational
  text. Here it runs locally via Ollama (Qwen2.5 7B).
- **Ollama** - A program that runs open AI models on your own computer.
- **Provider** - A place an AI model can be served from (local Ollama,
  or cloud NVIDIA).
- **Skill** - A small module that understands one area of speech and
  performs one area of work (timers, weather, files, ...).
- **Router** - The central function that takes any text and decides who
  handles it (command, skill, or conversation).
- **Parser** - Turns raw text into a command + arguments, stripping
  wake words and mapping aliases.
- **STT / TTS** - Speech-To-Text (understanding you) and Text-To-Speech
  (talking back).
- **Wake word** - The phrase ("Hey Jarvis") that activates listening in
  standby mode.
- **HUD** - Head-Up Display; here, the futuristic browser dashboard.
- **HTTP API / endpoint** - The way the web page and server talk
  (`/api/run` etc. are endpoints).
- **JSON** - A simple text format for storing data.
- **psutil** - A Python library that reads real system numbers
  (CPU, RAM, disk, battery, processes).
- **Regex** - A text pattern matching tool, used for wake words and
  skill phrasing.
- **Loopback** - The same-computer network address (127.0.0.1); traffic
  never leaves this machine.
- **VRAM** - The graphics card's memory, where the AI model runs.
- **Token** - A piece of text (roughly a word fragment) an AI model
  processes or generates; "37 tokens/s" is generation speed.
- **Gate script** - The project's hardware capability checker
  (scripts/gate.py).

---

## 13. Where to look for what (file shortcuts)

| If you want to see... | Open |
|-----------------------|------|
| How commands are routed | jarvis/main.py (Router.run) |
| How speech becomes commands | jarvis/core/parser.py |
| How voice/wake word works in the browser | frontend/app.js (search "ASSIST LOOP") |
| How skills are registered | jarvis/skills/__init__.py |
| How the AI provider is chosen | jarvis/modules/llm.py |
| How apps open and are verified | jarvis/modules/apps.py |
| The web server + security gate | server.py (search "_bridge_trusted") |
| The improvement plan | docs/JARVIS_ROADMAP.md |
| Setup + command list | README.md |
