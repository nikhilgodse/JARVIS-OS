# JARVIS OS Roadmap

Architect review of the repository as it stands. Every claim below was
checked against source; file pointers are given so each item is auditable.
Guiding rule for all phases: small, reviewable increments. No wholesale
rewrites, no fashion infrastructure.

## 1. Architecture summary

```
Terminal REPL                    Browser HUD
jarvis/main.py (Router)          server.py (WebRouter : Router) + frontend/
        \                              / frontal single files:
         \                            /  index.html, app.js, styles.css
          v                          v
   jarvis/core/parser.py      (wake-word strip, aliases)
   jarvis/skills/__init__.py  (SKILL_LIST dispatch: whatsapp, files,
                               opener, pc, system, maths, notes, timers,
                               weather, websearch, wikipedia)
   jarvis/modules/chat.py     (local replies -> skills -> llm.complete)
   jarvis/modules/llm.py      (provider router: Ollama primary on
                               127.0.0.1:11434, NVIDIA NIM fallback/cloud)
   jarvis/utils/storage.py    (JSON files under data/: config, notes,
                               timers, results, pending_confirm)
server.py additionally: ThreadingHTTPServer bound to 127.0.0.1:8000,
  GET /api/status|telemetry|weather|logs|providers (public),
  POST /api/run|login|transcribe. One global Router + chat history +
  scheduler shared by all browser sessions.
Voice: browser Web Speech API (primary) or server /api/transcribe
  (SpeechRecognition -> Google cloud STT). TTS via speechSynthesis
  (+ optional server speakers).
Tests: tests/ unittest suite (run: python -m unittest discover -s tests).
```

CLI and HUD already call the same Router/skills, which is the design to
preserve: one assistant runtime, two frontends.

## 2. Top risks, ranked by user impact

1. **HUD fabricates command success (HIGH).** `frontend/app.js`
   `handleCommand()` catch path: when `/api/run` fails after a good
   probe, it prints `Created X.`, `Removed X.`, `Task scheduled…`,
   `Launching X…` and even `Access granted. Welcome, sir.` None of it
   ran. A user can believe files were deleted/created or the machine
   is secured when nothing happened (or the opposite).
2. **No server-side authorization on machine-control endpoints (HIGH).**
   `server.py` `do_POST /api/run` executes arbitrary assistant
   commands (open apps, type keystrokes, close apps, shutdown flow)
   with no credential. The only boundary is the loopback bind
   (`ThreadingHTTPServer(("127.0.0.1", …))`), which does not stop other
   local processes or DNS-rebinding / cross-origin browser attacks.
   The `/api/login` + `auth` module do not gate commands (explicit
   comment at `server.py:190` documents this as a deliberate choice).
3. **Fictional status presented as live (MEDIUM).** `app.js:70-72`
   seeds an invented boot dialogue; `pollTelemetry` catch paints
   random CPU/RAM/disk (`Math.random`, `app.js:177`); core temp is
   estimated from CPU load (`36 + cpu/100*28`, `app.js:123`) with no
   sensor and no "estimated" label; the status line shows
   `LLM CONNECTED (model)` from the `configured` flag (`app.js:200`)
   while the backend already reports real health
   (`providers.primary_health`: `server_reachable`,
   `model_available`, `status`) that the HUD ignores.
4. **Mic audio leaves the device with no explicit consent surface
   (MEDIUM).** Server fallback STT is `recognize_google`
   (`server.py:381`); browser STT is also a cloud service. Nothing in
   the HUD states which path is active or what receives the audio.
5. **Shared conversational state (MEDIUM).** One global Router, chat
   history and pending confirmations in `server.py` are shared by all
   browser sessions/tabs. Notes/config are plain JSON in `data/`
   with no documented retention, review, or deletion path in the HUD
   (terminal has `reset`).
6. **No frontend test harness (LOW, process risk).** `app.js` is a
   ~1200-line single file; Python tests cannot cover it. Changes
   there are currently review-only.

Deliberately out of scope: performance tuning of the LLM path,
multi-machine deployment, non-Windows platforms (Windows first).

## 3. Phased roadmap

### Phase 0 - Trust, safety, truthful status (do first)
Outcome: the HUD never claims an action ran unless the backend
confirmed it; loopback API has a real authorization boundary;
status reflects measured health.
- Remove simulated success from `handleCommand` failure paths;
  keep only provably-local actions offline (help text, feed clear,
  local TTS, mic toggle); honest "not executed" error otherwise.
- Show explicit OFFLINE telemetry (dashes), never random drift;
  replace the fictional seed dialogue with a real probe result;
  label core temp EST (no Windows sensor available via stdlib).
- Drive the LLM status line from `providers.primary_health.status`
  (`online`/`degraded`/…), never from the `configured` flag.
- Gate state-changing endpoints: Host/Origin validation on POST
  `/api/*` (loopback-only, no UX change, terminal untouched) as the
  first boundary; per-client token as a follow-up (see §5).
- Document the loopback threat model and the STT data flow
  (browser STT vs server→Google) where the user will see it.
- Acceptance: backend-down drills show accurate UI; spoofed
  Host/Origin POSTs get 403; no success-claim strings remain in the
  normal command path; focused regression tests cover each item.

### Phase 1 - A clean assistant core
Outcome: adding a skill/provider never means editing a giant
conditional; sessions stop sharing state.
- Introduce a tiny typed tool-result schema (`ok`, `reply`,
  `needs_confirm`, `error`) behind the existing skill functions;
  keep all current behavior.
- Split WebRouter session state per browser session (token or
  cookie); isolate chat history and pending confirmations.
- Add per-request timeouts, structured errors, bounded history.
- Acceptance: a new skill is one registered module + tests; two
  tabs hold independent conversations (tested).

### Phase 2 - Better conversations and user-controlled memory
Outcome: memory the owner can see, fix, and wipe.
- HUD memory view: list/edit/delete/export/reset notes; retention
  setting; never persist secrets as notes (warn on key-like text).
- Multi-turn context controls; cite sources with freshness for
  web-backed answers; mark estimates vs measurements.
- Acceptance: memory CRUD + reset tested end-to-end; secrets
  warning tested.

### Phase 3 - Voice with visible privacy
Outcome: the owner always knows where audio goes and can stop it.
- Pluggable STT/TTS providers (browser, server-Google, local
  option); HUD badge shows the active path; consent toggle before
  server transcription; no continuous recording without an
  explicit indicator.
- Push-to-talk reliability, barge-in, no-speech handling,
  per-utterance language setting.
- Acceptance: path badge + consent + instant stop tested; STT
  destination documented per provider.

### Phase 4 - Reliable, declared tools
Outcome: every integration states what it can do and proves it.
- Tool catalog entries: inputs, permission level, risk,
  timeout, dry-run where meaningful, audit log line.
- Least-privilege credentials for cloud services; confirmations
  enforced server-side; tool output treated as untrusted.
- Acceptance: each tool has failure/refusal tests; no path lets
  the LLM run raw shell or skip confirmation.

### Phase 5 - Product quality and release readiness
Outcome: measurable, shippable, maintainable.
- HUD responsiveness/keyboard/screen-reader pass; onboarding and
  error states; settings UI for provider/voice/memory.
- JS unit harness for `app.js` pure logic; versioned
  conversation-eval set (task success, false-success claims,
  confirmation bypasses, latency, provider failures).
- Packaging, backup/migration, release checklist.
- Acceptance: eval set runs green; metrics recorded per release.

## 4. What Jarvis can do today / cannot do yet

Can (with backend + providers up; see `jarvis/skills/`,
`tests/test_*`):
open apps/sites/YouTube + play (`skills/opener.py`), PC volume /
brightness / media / screenshot / clipboard (`skills/pc.py`,
`modules/pccontrol.py`), files find/open/create/delete with
confirmation (`skills/files.py`, `skills/confirm.py`), timers
(`skills/timers.py`), notes remember/recall (`skills/notes.py`),
weather via Open-Meteo (`skills/weather.py`), Wikipedia/ DuckDuckGo
summaries (`skills/wikipedia.py`, `skills/websearch.py`), mental
math (`skills/maths.py`), WhatsApp send with preview+confirm
(`skills/whatsapp.py`), LLM chat via Ollama/NVIDIA
(`modules/llm.py`), voice input + wake word (`frontend/app.js`).

Cannot yet: prove an action ran when the backend is flaky (§2.1);
refuse non-loopback API callers (§2.2); distinguish estimated vs
measured telemetry (§2.3); show or consent STT routing (§2.4);
isolate sessions or manage memory from the HUD (§2.5/Phase 2);
stream LLM replies; image/file understanding; run without the
loopback bridge for remote access (by design, keep it that way).

## 5. Notes and open decisions
- Auth follow-up: per-start random token issued to the served HUD
  (SOP-kept) + required on POST. Stronger than Host/Origin checks
  (covers malicious local processes) but adds token plumbing and a
  lockout risk; do it in Phase 0-part-2, not in the first slice.
- `auth`/`DEFAULT_PASSWORD` + `/api/login` predate the loopback-only
  decision; either wire login to real gating (with the token above)
  or remove the password theater. Do not ship both.
- `data/` JSON holds notes/timers/config: Phase 2 adds retention +
  HUD deletion. Never log audio, keys, or message bodies.
