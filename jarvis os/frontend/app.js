/* ============================================================
   JARVIS HUD -- frontend only
   Voice input with state machine, PTT, hands-free, live transcript
   ============================================================ */
const API_BASE = "";

const feed = document.getElementById('feed');
const cmdInput = document.getElementById('cmdInput');
const statusBanner = document.getElementById('statusBanner');
const statusText = document.getElementById('statusText');

/* ---------- helpers ---------- */
function now() {
  const d = new Date();
  return d.toTimeString().slice(0, 8);
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function addMsg(who, text, cls = 'ai') {
  const el = document.createElement('div');
  el.className = 'msg ' + cls;
  const safe = escapeHtml(text).replace(/\n/g, '<br>');
  el.innerHTML = `<div class="who"><span>● ${escapeHtml(who)}</span><span class="time">${now()}</span></div><div class="msg-body">${safe}</div>`;
  feed.appendChild(el);
  feed.scrollTop = feed.scrollHeight;
}
let voiceOutActive = false;
function speak(text) {
  try {
    if ('speechSynthesis' in window) {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 1.06; u.pitch = 0.8;
      u.onstart = () => { voiceOutActive = true; };
      u.onend = u.onerror = () => { voiceOutActive = false; };
      speechSynthesis.speak(u);
    }
  } catch (e) {}
}

/* JARVIS keeps it to what is necessary.
   Routine answers stay on screen. He talks back when he actually needs an
   answer out of you, or when you told him to ("speak <text>", "voice on"). */
let voiceReplies = false;
try { voiceReplies = localStorage.getItem('jarvis_voice_out') === '1'; } catch {}

function needsVoice(text) {
  const t = (text || '').trim();
  if (!t) return false;
  if (voiceReplies) return true;
  // A short question is the one case where staying silent leaves you hanging.
  return t.length <= 160 && /\?\s*$/.test(t);
}

function maybeSpeak(text) {
  const t = (text || '').replace(/^[\s✔✖⚠─]+/gm, '').trim();
  if (t && needsVoice(t)) speak(t);
}

function setVoiceReplies(on) {
  voiceReplies = !!on;
  try { localStorage.setItem('jarvis_voice_out', on ? '1' : '0'); } catch {}
  addMsg('JARVIS_AI', on
    ? 'Voice replies on.'
    : 'Voice replies off. I will keep it to what matters.');
}

/* ---------- seed feed ---------- */
// Honest boot line only. Backend state is unknown until probeBackend()
// answers; nothing here may claim systems are online or quote telemetry.
addMsg('JARVIS_AI', 'HUD loaded. Probing backend…');

/* ---------- temporal sync clock ---------- */
const syncEl = document.getElementById('syncTime');
setInterval(() => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const s = `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  syncEl.textContent = s;
  if (coreSubEl) coreSubEl.textContent = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}, 1000);

/* ---------- reactor core state ---------- */
const coreStateEl = document.getElementById('coreState');
const coreSubEl = document.getElementById('coreSub');
const corePowerEl = document.querySelector('#corePower i');
let coreMode = 'boot';
function setCoreState(s) {
  const map = {
    online: ['ONLINE', ''], listening: ['LISTENING', 'st-listening'],
    thinking: ['THINKING', 'st-thinking'], responding: ['RESPONDING', 'st-responding'],
    offline: ['OFFLINE', 'st-offline'],
  };
  const [txt, cls] = map[s] || map.online;
  coreMode = s;
  coreStateEl.textContent = txt;
  coreStateEl.className = 'core-state' + (cls ? ' ' + cls : '');
}
function restoreCoreState(delay = 2500) {
  setTimeout(() => {
    if (['thinking', 'responding', 'listening'].includes(coreMode))
      setCoreState(backendOnline ? 'online' : 'offline');
  }, delay);
}

/* ---------- live telemetry ---------- */
const cpuBar = document.getElementById('cpuBar'), cpuVal = document.getElementById('cpuVal');
const tempBar = document.getElementById('tempBar'), tempVal = document.getElementById('tempVal');
const ramBar = document.getElementById('ramBar'), ramVal = document.getElementById('ramVal');
const slot4Bar = document.getElementById('slot4Bar'), slot4Val = document.getElementById('slot4Val'), slot4Label = document.getElementById('slot4Label');
const cpuCoreLabel = document.getElementById('cpuCoreLabel'), ramTotalLabel = document.getElementById('ramTotalLabel');
const weatherVal = document.getElementById('weatherVal'), ipVal = document.getElementById('ipVal'), locVal = document.getElementById('locVal');
const arcCpu = document.getElementById('arcCpu'), arcRam = document.getElementById('arcRam'), arcDsk = document.getElementById('arcDsk');
const chipCpu = document.getElementById('chipCpu'), chipRam = document.getElementById('chipRam'),
      chipTemp = document.getElementById('chipTemp'), chipUp = document.getElementById('chipUp');
let backendOnline = false;
function paintReactor(cpu, ram, dsk, up, meta) {
  cpu = Math.max(0, Math.min(100, cpu)); ram = Math.max(0, Math.min(100, ram)); dsk = Math.max(0, Math.min(100, dsk));
  arcCpu.style.strokeDasharray = `${cpu} 100`;
  arcRam.style.strokeDasharray = `${ram} 100`;
  arcDsk.style.strokeDasharray = `${dsk} 100`;
  const tmp = 36 + (cpu / 100) * 28; // ESTIMATE from load: no temp sensor
  // is exposed here (Windows stdlib has none). Labelled EST in the HUD.
  cpuBar.style.width = cpu + '%'; cpuVal.textContent = cpu.toFixed(1) + '%';
  ramBar.style.width = ram + '%'; ramVal.textContent = ram.toFixed(1) + '%';
  tempBar.style.width = ((tmp - 30) / 70 * 100) + '%'; tempVal.textContent = tmp.toFixed(1) + '°C';
  chipCpu.textContent = cpu.toFixed(0) + '%'; chipRam.textContent = ram.toFixed(0) + '%';
  chipTemp.textContent = tmp.toFixed(0) + '°C'; chipUp.textContent = up || '--';
  if (corePowerEl) corePowerEl.style.width = Math.max(15, 100 - cpu * 0.6) + '%';
  if (meta) {
    if (cpuCoreLabel && meta.cpu_count) cpuCoreLabel.textContent = `CPU LOAD (${meta.cpu_count} CORES)`;
    if (ramTotalLabel && meta.mem_total) ramTotalLabel.textContent = `RAM (${Math.round(meta.mem_total / (1024**3))} GB)`;
    if (slot4Label && slot4Val && slot4Bar) {
      if (meta.battery_pct !== null && meta.battery_pct !== undefined) {
        slot4Label.textContent = `BATTERY (${meta.battery_plugged ? 'CHARGING' : 'BATTERY'})`;
        slot4Val.textContent = `${meta.battery_pct}%`;
        slot4Bar.style.width = `${meta.battery_pct}%`;
      } else {
        slot4Label.textContent = 'STORAGE / DISK';
        slot4Val.textContent = `${dsk.toFixed(1)}%`;
        slot4Bar.style.width = `${dsk}%`;
      }
    }
    if (ipVal && meta.local_ip) ipVal.textContent = meta.local_ip;
    if (locVal && meta.location) locVal.textContent = meta.location.toUpperCase();
  }
}

let lastWeatherCheck = 0;
async function updateWeather() {
  const tNow = Date.now();
  if (tNow - lastWeatherCheck < 45000) return;
  lastWeatherCheck = tNow;
  try {
    const r = await fetch(API_BASE + '/api/weather', { cache: 'no-store' });
    if (!r.ok) return;
    const data = await r.json();
    if (data && data.weather && weatherVal) {
      let w = data.weather;
      if (w.includes(':')) w = w.split(':')[1].trim();
      if (w.length > 22) w = w.slice(0, 22) + '..';
      weatherVal.textContent = w.toUpperCase();
      if (locVal && data.city) locVal.textContent = data.city.toUpperCase();
    }
  } catch {}
}

async function pollTelemetry() {
  try {
    const r = await fetch(API_BASE + '/api/telemetry', { cache: 'no-store' });
    if (!r.ok) throw 0;
    const t = await r.json();
    paintReactor(Number(t.cpu_load) || 0, Number(t.mem_pct) || 0, Number(t.disk_pct) || 0, t.uptime, t);
    updateWeather();
    return;
  } catch { paintOffline(); }
}

// No backend, no numbers: show an explicit offline state. Random drift
// values were previously painted here and read as live telemetry.
function paintOffline() {
  cpuBar.style.width = '0%'; cpuVal.textContent = '--';
  tempBar.style.width = '0%'; tempVal.textContent = '--';
  ramBar.style.width = '0%'; ramVal.textContent = '--';
  chipCpu.textContent = '--'; chipRam.textContent = '--';
  chipTemp.textContent = '--'; chipUp.textContent = 'OFFLINE';
  if (slot4Val) slot4Val.textContent = '--';
}
setInterval(pollTelemetry, 2000);
pollTelemetry();

if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const loc = document.getElementById('locVal');
      if (loc && loc.textContent === 'OFFLINE') loc.textContent = `${pos.coords.latitude.toFixed(2)}, ${pos.coords.longitude.toFixed(2)}`;
    },
    () => {}, { timeout: 4000 }
  );
}

/* ---------- backend status probe ---------- */
let _probeSaid = false;
async function probeBackend() {
  try {
    const r = await fetch(API_BASE + '/api/status', { cache: 'no-store' });
    if (!r.ok) throw 0;
    const s = await r.json();
    backendOnline = true;
    statusBanner.classList.add('online'); statusBanner.classList.remove('error');
    // Health, not config: `configured` is true for the stock Ollama URL even
    // with no server behind it. primary_health carries the measured
    // server_reachable / model_available / status from the backend.
    const ph = (s.providers && s.providers.primary_health) || {};
    const model = (s.llm && s.llm.model) || 'no model';
    const state = String(ph.status || 'unknown').toUpperCase();
    const llmText = state === 'ONLINE' ? `CONNECTED (${model})` : `${state} (${model})`;
    statusText.textContent = `JARVIS CORE ONLINE - ${s.snapshot.hostname} · ${s.snapshot.platform} · LLM ${llmText}${s.providers ? ' · PROVIDER: ' + s.providers.primary.toUpperCase() : ''}`;
    if (!_probeSaid) { _probeSaid = true; addMsg('JARVIS_AI', 'Backend reachable. Systems nominal.'); }
    if (['boot', 'offline', 'online'].includes(coreMode)) setCoreState('online');
    return;
  } catch {
    backendOnline = false;
    statusBanner.classList.add('error'); statusBanner.classList.remove('online');
    statusText.textContent = 'BACKEND OFFLINE - Run: python server.py, then open http://127.0.0.1:8000';
    if (!_probeSaid) { _probeSaid = true; addMsg('JARVIS_AI', 'Backend unreachable. Showing offline state; commands will not run.'); }
    if (['boot', 'online', 'offline'].includes(coreMode)) setCoreState('offline');
  }
}
probeBackend(); setInterval(probeBackend, 5000);

/* ---------- file:// guard ---------- */
if (window.location && window.location.protocol === 'file:') {
  statusBanner.classList.add('error'); statusBanner.classList.remove('online');
  statusText.textContent = 'WRONG LAUNCH - CLOSE THIS FILE, RUN: python server.py, OPEN: http://127.0.0.1:8000';
  addMsg('JARVIS_AI', 'This page was opened as a file, so the mic, commands and live data cannot work. Run "python server.py", then open http://127.0.0.1:8000 in your browser.');
}

/* ---------- background log stream ---------- */
let logCursor = null;
async function pollLogs() {
  try {
    const r = await fetch(API_BASE + '/api/logs' + (logCursor === null ? '' : '?since=' + logCursor), { cache: 'no-store' });
    if (!r.ok) return;
    const j = await r.json();
    if (logCursor === null) { logCursor = j.cursor; return; }
    logCursor = j.cursor;
    for (const e of (j.logs || [])) addMsg('JARVIS_SYS', e.text, 'sys');
  } catch {}
}
setInterval(pollLogs, 3000); pollLogs();

/* ---------- command router ---------- */
const ALIASES = {
  status: ['status','stats','dash','dashboard','system'],
  scan: ['scan','processes','procs','ps'],
  open: ['open','launch','run','start'],
  search: ['search','find','locate','glob'],
  navigate: ['cd','navigate','go','chdir'],
  list: ['list','ls','dir'],
  create: ['create','mkdir','touch','new'],
  remove: ['remove','rm','delete','del','remove-item'],
  copy: ['copy','cp','copy-item'],
  move: ['move','mv','move-item'],
  automate: ['automate','schedule','task','cron'],
  jobs: ['jobs','scheduled','list-tasks'],
  chat: ['chat','ask','ai'],
  speak: ['speak','say','talk','tts'],
  voice: ['voice','listen','mic','hear'],
  reset: ['reset','forget','clear-chat'],
  brain: ['brain','model','llm','api'],
  skills: ['skills','capabilities','abilities','features'],
  location: ['location','set-location','set location','where am i','home'],
  pc: ['pc','pccontrol','automate-pc','pc control'],
  doctor: ['doctor','diag','diagnostic','health'],
  help: ['help','h','?'],
  clear: ['clear','cls'],
  shutdown: ['shutdown','exit','quit','bye','powerdown','power off'],
  authenticate: ['login','signin','auth','access'],
};
function parseCmd(raw) {
  const cleaned = raw.trim();
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (!parts.length) return { command: null, args: [] };
  const words_lower = parts.map(p => p.toLowerCase());
  const maxWords = Math.min(parts.length, 4);
  for (let n = maxWords; n >= 1; n--) {
    const candidate = words_lower.slice(0, n).join(' ');
    for (const [canon, aliases] of Object.entries(ALIASES)) {
      if (aliases.includes(candidate)) {
        return { command: canon, args: parts.slice(n), raw: cleaned };
      }
    }
  }
  return { command: 'chat', args: parts.slice(1), raw: cleaned, implicit: true };
}

const cmdHistory = [];
let historyIndex = -1;

async function handleCommand(raw) {
  const text = raw.trim();
  if (!text) return;
  if (!cmdHistory.length || cmdHistory[cmdHistory.length - 1] !== text) {
    cmdHistory.push(text);
  }
  historyIndex = -1;
  addMsg('>_USER_COMMAND', text, 'user');
  const { command, args } = parseCmd(text);

  setCoreState('thinking');
  try {
    const r = await fetch(API_BASE + '/api/run', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ command: text }) });
    if (!r.ok) throw 0;
    const j = await r.json();
    const reply = (j.reply || '(no reply)').slice(0, 6000);
    addMsg('JARVIS_AI', reply);
    if (command === 'clear') feed.innerHTML = '';
    if (command === 'shutdown') showShutdown();
    maybeSpeak(reply);
    setCoreState('responding'); restoreCoreState();
    probeBackend();
    return;
  } catch {
    if (!backendOnline) {
      addMsg('JARVIS_AI', 'Server offline -- run: python server.py, then refresh this page.');
      setCoreState('offline'); restoreCoreState();
      return;
    }
  }
  backendOnline = false;

  // The request failed but an earlier probe said online: the backend died
  // in between. NOTHING below may claim a server-side effect happened.
  // Only provably-local actions run here (help text, feed clear, local
  // TTS, mic toggle, clock answers). Everything else gets one honest
  // error: not executed, retry after the server is back.
  const NOT_EXECUTED = 'Backend unreachable -- nothing was executed. Start the server, then retry.';
  switch (command) {
    case 'help':
      addMsg('JARVIS_AI', 'Manual: status · scan · open <app> · ls · cd · create · remove · copy · move · search · automate · jobs · chat · speak · voice · brain · login · clear · shutdown');
      break;
    case 'speak': { const t = args.join(' '); addMsg('JARVIS_AI', t || 'Usage: speak <text>'); if (t) speak(t); break; }
    case 'voice': {
      const sub = (args[0] || '').toLowerCase();
      if (sub === 'on' || sub === 'off') { setVoiceReplies(sub === 'on'); break; }
      toggleMic(); addMsg('JARVIS_AI', 'Voice interface toggled.'); break;
    }
    case 'brain': addMsg('JARVIS_AI', 'LLM BRAIN: backend unreachable, so status is unknown. Setup: set JARVIS_LLM_API_KEY or run: brain set <api-key> [endpoint] [model]'); break;
    case 'clear': feed.innerHTML = ''; break;
    case 'shutdown': showShutdown(); break;
    default: {
      const q = text.toLowerCase();
      let reply = null;
      if (/time/.test(q)) reply = `The time is ${now()}, sir.`;
      else if (/date|day/.test(q)) reply = `Today is ${new Date().toDateString()}, sir.`;
      else if (/who are you|your name/.test(q)) reply = 'I am JARVIS -- Just A Rather Very Intelligent System, at your service.';
      else if (/^(hello|hi|hey)[\s,.!]*$/.test(q)) reply = 'At your service, sir. Backend is offline.';
      else if (/help/.test(q)) reply = 'Try: status, scan, ls, brain, or just talk to me naturally.';
      addMsg('JARVIS_AI', reply || NOT_EXECUTED);
      if (reply) maybeSpeak(reply);
    }
  }
  setCoreState('responding'); restoreCoreState();
}

/* ---------- input wiring ---------- */
document.getElementById('btnExecute').onclick = () => { handleCommand(cmdInput.value); cmdInput.value = ''; cmdInput.focus(); };
cmdInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    handleCommand(cmdInput.value);
    cmdInput.value = '';
  } else if (e.key === 'ArrowUp') {
    if (cmdHistory.length > 0) {
      e.preventDefault();
      if (historyIndex === -1) historyIndex = cmdHistory.length - 1;
      else if (historyIndex > 0) historyIndex--;
      cmdInput.value = cmdHistory[historyIndex] || '';
    }
  } else if (e.key === 'ArrowDown') {
    if (cmdHistory.length > 0 && historyIndex !== -1) {
      e.preventDefault();
      if (historyIndex < cmdHistory.length - 1) {
        historyIndex++;
        cmdInput.value = cmdHistory[historyIndex] || '';
      } else {
        historyIndex = -1;
        cmdInput.value = '';
      }
    }
  }
});

/* ---------- quick action chips ---------- */
document.querySelectorAll('.action-chip').forEach((btn) => {
  btn.addEventListener('click', () => {
    const cmd = btn.getAttribute('data-cmd');
    if (cmd) {
      cmdInput.value = '';
      handleCommand(cmd);
    }
  });
});

/* ---------- hide logs / terminate ---------- */
const logPanel = document.getElementById('logPanel');
document.getElementById('btnHideLogs').onclick = (e) => {
  const hidden = logPanel.style.display === 'none';
  logPanel.style.display = hidden ? '' : 'none';
  e.currentTarget.firstChild.textContent = hidden ? 'HIDE LOGS ' : 'SHOW LOGS ';
};
const overlay = document.getElementById('shutdownOverlay');
function showShutdown() { overlay.classList.remove('hidden'); addMsg('JARVIS_AI', 'Goodbye, sir. Shutting down gracefully.'); }
document.getElementById('btnTerminate').onclick = showShutdown;
document.getElementById('btnReboot').onclick = () => { overlay.classList.add('hidden'); addMsg('JARVIS_AI', 'Systems re-initialized. Welcome back, sir.'); };

/* ============================================================
   VOICE STATE MACHINE
   States: idle -> listening -> finalizing -> idle
   Click mic to start, click again to stop
   ============================================================ */

// --- DOM references ---
const btnMic = document.getElementById('btnMic');
const listenLabel = document.getElementById('listenLabel');
const btnStop = document.getElementById('btnStop');
const btnCancel = document.getElementById('btnCancel');
const transcriptPanel = document.getElementById('transcriptPanel');
const transcriptText = document.getElementById('transcriptText');
const transcriptState = document.getElementById('transcriptState');

// --- Voice state ---
let voiceMode = 'idle'; // idle | listening | finalizing
let recognizing = false;
let recog = null;
let recogGotResult = false;
let finalTranscript = '';
let lastResultCount = 0;
// True once the MIC produced text. Gates the cmdInput fallback so text the
// user typed is never mistaken for speech and executed hands-free.
let micHeardText = false;
// Set when the recogniser dies for a reason restarting cannot fix (mic
// blocked, no input device). Suppresses onend's auto-restart, which would
// otherwise error -> restart -> error in a ~20/s loop and flood the feed.
let voiceHalted = false;
let lastVoiceWarn = { msg: '', at: 0 };

/* --- Assist loop --------------------------------------------------------
   'off'         -> one command per click (original behaviour).
   'conversation'-> after an answer the mic reopens itself, so you keep
                    talking without touching anything.
   'standby'     -> mic stays open waiting for "Hey Jarvis"; only a wake
                    phrase gets through, everything else is ignored.
   sessionKind tells the recogniser which of the two it is running. */
let assistMode = 'off';           // 'off' | 'conversation' | 'standby'
let sessionKind = 'manual';       // 'manual' | 'command' | 'wake'
let resumeTimer = null;
// Anchored to the start of the utterance so "the actor named jarvis" is not
// mistaken for an address, and so the separator (",", ":") is consumed too.
const WAKE_RE_BARE = /^\s*(?:(?:hey|hi|ok|okay|yo)[\s,.]+)?jarvis\b[\s,.:;]*/i;
const ASSIST_EXIT_RE = /^(?:goodbye|good bye|bye|stop|stop listening|done|end|finished|that'?s all|that will be all|that would be all|i'?m done|go to sleep|stand down)\s*[.!?]?$/i;
const MIC_BLOCKED_MSG = 'Mic blocked -- allow microphone for this site, then reload (icon left of the address bar > Microphone > Allow).';

// --- Silence timer (backup only, explicit stop preferred) ---
let silenceTimer = null;
const SILENCE_DELAY = 8000; // 8s backup silence timer (generous)

// --- Auto-process guarantees ---------------------------------------------
// A spoken command must run on its own: after silence, or at the latest
// when a hard cap is reached. Without these, a session can sit in
// "listening" forever and never dispatch (the reported bug).
const MAX_LISTEN_MS = 30000;     // browser STT: never listen longer than this
const FALLBACK_SILENCE_MS = 1600; // server STT: quiet this long => speech done
const FALLBACK_MAX_MS = 20000;    // server STT hard cap
const VOICE_THRESHOLD = 0.02;     // peak amplitude counted as speech

// --- Voice watchdog (browser STT auto-finalize) ---
let watchdogTimer = null;
let listenStartedAt = 0;
let lastActivityAt = 0;

function stopVoiceWatchdog() {
  clearInterval(watchdogTimer);
  watchdogTimer = null;
}

// Text the mic actually produced. Falls back to the input box only when the
// recogniser delivered interim results and never a final one; without this a
// spoken command shows up in the bar and is then silently discarded.
function heardFromMic() {
  if (finalTranscript.trim()) return finalTranscript.trim();
  return micHeardText ? cmdInput.value.trim() : '';
}

function startVoiceWatchdog() {
  stopVoiceWatchdog();
  listenStartedAt = Date.now();
  lastActivityAt = Date.now();
  watchdogTimer = setInterval(() => {
    if (voiceMode !== 'listening') { stopVoiceWatchdog(); return; }
    const now = Date.now();
    const heard = heardFromMic();
    if (heard && now - lastActivityAt >= SILENCE_DELAY) {
      addMsg('JARVIS_AI', 'Silence detected. Processing...');
      finalizeVoice();
      return;
    }
    // Standby is meant to run indefinitely; the hard cap only exists so a
    // command session cannot sit open forever.
    if (sessionKind !== 'wake' && now - listenStartedAt >= MAX_LISTEN_MS) {
      addMsg('JARVIS_AI', 'Listening time limit reached. Processing...');
      finalizeVoice();
    }
  }, 400);
}

// --- Explicit end-of-speech commands ---
const END_COMMANDS = /^(that'?s all|stop listening|stop|done|execute|go ahead|process that|that'?s it|finish|end|complete|send it|i'?m done|that will be all|that would be all|that's it|cancel)\s*[.!?]?$/i;

// --- Fallback WAV recorder ---
let fallbackStream = null;

/* --- UI helpers --- */
function setListenLabel(html, recording) {
  listenLabel.innerHTML = `<span class="cyan-dot"></span> ${escapeHtml(html)}`;
  listenLabel.classList.toggle('recording', !!recording);
}

function showVoiceControls(show) {
  if (btnStop) btnStop.style.display = show ? '' : 'none';
  if (btnCancel) btnCancel.style.display = show ? '' : 'none';
}

function showTranscriptPanel(show) {
  transcriptPanel.classList.toggle('hidden', !show);
}

function updateTranscriptDisplay(text, isFinal) {
  if (!text) {
    transcriptText.textContent = 'Waiting for voice input...';
    transcriptText.className = 'transcript-text empty';
  } else {
    transcriptText.textContent = text;
    transcriptText.className = 'transcript-text' + (isFinal ? ' final' : '');
  }
}

function setTranscriptState(state) {
  transcriptState.textContent = state;
}

/* --- Silence timer --- */
function resetSilenceTimer() {
  clearTimeout(silenceTimer);
  silenceTimer = null;
}

function startSilenceTimer() {
  resetSilenceTimer();
  silenceTimer = setTimeout(() => {
    if (voiceMode === 'listening' && heardFromMic()) {
      addMsg('JARVIS_AI', 'Silence detected. Processing...');
      finalizeVoice();
    }
  }, SILENCE_DELAY);
}

/* --- End command detection --- */
function detectEndCommand(text) {
  return END_COMMANDS.test(text.trim());
}

/* --- Interrupt: stop TTS if speaking --- */
function interruptIfNeeded() {
  if (voiceOutActive || (window.speechSynthesis && speechSynthesis.speaking)) {
    try { speechSynthesis.cancel(); } catch {}
    voiceOutActive = false;
    addMsg('JARVIS_AI', '(interrupted)');
  }
}

/* ============================================================
   WEB SPEECH API (Browser STT)
   ============================================================ */
/* ============================================================
   ASSIST LOOP (wake word + auto re-listen)
   ============================================================ */
function renderAssistBtn() {
  const b = document.getElementById('btnAssist');
  if (!b) return;
  const label = { off: 'ASSIST: OFF', conversation: 'ASSIST: TALK', standby: 'ASSIST: STANDBY' }[assistMode] || 'ASSIST: OFF';
  b.textContent = label;
  b.classList.toggle('on', assistMode !== 'off');
  b.title = assistMode === 'standby'
    ? 'Standing by for "Hey Jarvis". Click to change.'
    : 'Click to change hands-free mode.';
}

function setAssistMode(mode) {
  assistMode = mode;
  try { localStorage.setItem('jarvis_assist', mode); } catch {}
  renderAssistBtn();
  // Keep an already-open session in step with the new mode, otherwise
  // standing down or switching to conversation would leave a wake session
  // that keeps ignoring every command you give it.
  if (voiceMode !== 'listening') return;
  if (mode === 'off') { cancelVoice(); return; }
  const want = mode === 'standby' ? 'wake' : 'command';
  if (sessionKind !== want) startListening(want);
}

function cycleAssistMode() {
  const order = ['off', 'conversation', 'standby'];
  const next = order[(order.indexOf(assistMode) + 1) % order.length];
  clearTimeout(resumeTimer);
  const wasListening = voiceMode === 'listening';
  setAssistMode(next);

  if (next === 'off') {
    addMsg('JARVIS_AI', 'Hands-free off. Click the mic when you need something.');
    return false;
  }
  if (next === 'conversation') {
    addMsg('JARVIS_AI', 'I will keep the mic open after each answer. Say "stop listening" to end.');
    if (!wasListening) startListening('command');
    return false;
  }
  addMsg('JARVIS_AI', 'Standing by. Say "Hey Jarvis" and I will pick up.');
  if (!wasListening) startWakeSession();
  return false;
}

// Pull the wake phrase out of a committed result.
// Returns the leftover command, '' if only the wake word was said, or null
// if the utterance was not addressed to him at all.
function extractWake(text) {
  const t = (text || '').trim();
  const m = WAKE_RE_BARE.exec(t);
  if (!m) return null;
  return t.slice(m[0].length).trim();
}

// Arm an already-spoken command so the normal silence/finalize path runs.
function extractCommand(heard) {
  const text = (heard || '').trim();
  sessionKind = 'command';
  if (!text) {
    setTranscriptState('LISTENING');
    setListenLabel('LISTENING... GO AHEAD', true);
    startVoiceWatchdog();
    return;
  }
  finalTranscript = text + ' ';
  micHeardText = true;
  cmdInput.value = text;
  updateTranscriptDisplay(text, false);
  setTranscriptState('LISTENING');
  setListenLabel('LISTENING... GO AHEAD', true);
  startSilenceTimer();
  startVoiceWatchdog();
}

// Detach the live recogniser outright. recog.stop() leaves `recognizing`
// true until onend arrives, and startWebSpeech() then bails out through its
// own "already running" guard -- so switching between wake and command
// sessions could quietly keep running the old one.
function hardStopRecognizer() {
  if (recog) {
    recog.onresult = recog.onend = recog.onerror = recog.onnomatch = null;
    try { recog.abort(); } catch {}
  }
  recognizing = false;
  resetSilenceTimer();
  stopVoiceWatchdog();
}

// One copy of a warning per short window: a restarting recogniser can fire
// the same error dozens of times a second and bury everything else.
function warnVoiceOnce(msg) {
  const now = Date.now();
  if (lastVoiceWarn.msg === msg && now - lastVoiceWarn.at < 15000) return;
  lastVoiceWarn = { msg, at: now };
  addMsg('JARVIS_AI', msg);
}

// Kill the session for errors a restart cannot cure. Sets voiceMode first,
// because Chrome fires onend straight after onerror and onend would otherwise
// call recog.start() again -- restarting the very thing that just failed.
function haltVoiceOnError(msg) {
  voiceMode = 'idle';
  voiceHalted = true;
  recognizing = false;
  stopVoiceWatchdog();
  resetSilenceTimer();
  btnMic.classList.remove('active');
  showVoiceControls(false);
  setListenLabel(msg, false);
  setTranscriptState('ERROR');
  warnVoiceOnce(msg);
}

function startListening(kind) {
  sessionKind = kind || 'command';
  clearTimeout(resumeTimer);
  voiceHalted = false;
  if (recognizing) hardStopRecognizer();
  const mode = getSttMode();
  const hasBrowserSTT = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  if (mode === 'server' || !hasBrowserSTT) {
    if (!fallbackStream) startFallbackRecord();
    return;
  }
  if (fallbackStream) stopFallbackRecord(true);
  startWebSpeech();
}

function startWakeSession() { startListening('wake'); }

// After an answer, pick the session back up unless you ended it by hand.
function resumeAfterAnswer() {
  clearTimeout(resumeTimer);
  if (assistMode === 'off' || voiceMode !== 'idle') return;
  resumeTimer = setTimeout(() => {
    if (assistMode === 'off' || voiceMode !== 'idle') return;
    if (assistMode === 'standby') startWakeSession();
    else startListening('command');
  }, 1100);
}

function startWebSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return false;
  if (recognizing) {
    if (voiceMode === 'listening') { try { recog.stop(); } catch {} return true; }
    // Stale session left behind by an interrupted run: it used to make this
    // function bail out early, so clicking the mic appeared to do nothing.
    if (recog) {
      recog.onresult = recog.onend = recog.onerror = recog.onnomatch = null;
      try { recog.abort(); } catch {}
    }
    recognizing = false;
  }

  recog = new SR();
  recog.lang = 'en-US';
  recog.interimResults = true;
  recog.maxAlternatives = 1;
  recog.continuous = true;
  recogGotResult = false;
  finalTranscript = '';
  lastResultCount = 0;
  micHeardText = false;
  resetSilenceTimer();

  voiceMode = 'listening';
  btnMic.classList.add('active');
  showVoiceControls(true);
  showTranscriptPanel(true);
  updateTranscriptDisplay('', false);
  setTranscriptState(sessionKind === 'wake' ? 'STANDBY' : 'LISTENING');
  setListenLabel(sessionKind === 'wake' ? 'STANDBY... SAY "HEY JARVIS"' : 'LISTENING... SPEAK NOW', true);
  recognizing = true;
  setCoreState('listening');
  interruptIfNeeded();
  startVoiceWatchdog();

  recog.onresult = (e) => {
    lastActivityAt = Date.now();
    // Iterate from resultIndex, never from our own forward counter. Chrome
    // rewrites an in-progress utterance AT ITS EXISTING INDEX and only flips
    // isFinal on it once you stop speaking -- so advancing lastResultCount
    // after the first interim steps straight over the commit. That killed the
    // wake word outright and left every command frozen on its first draft.
    const from = (typeof e.resultIndex === 'number' && e.resultIndex >= 0) ? e.resultIndex : 0;
    for (let i = from; i < e.results.length; i++) {
      const res = e.results[i];
      const t = res[0] ? res[0].transcript : '';
      // A browser that always reports resultIndex 0 must not let us take the
      // same committed result twice and duplicate finalTranscript.
      if (res.isFinal && i < lastResultCount) continue;

      // Standby: nothing is a command until he hears his name. Everything
      // else is background noise and is dropped without a trace.
      if (sessionKind === 'wake') {
        if (!res.isFinal) continue;        // only committed speech can wake him
        lastResultCount = i + 1;
        const rest = extractWake(t);
        if (rest === null) continue;
        updateTranscriptDisplay((rest || '...').trim(), false);
        extractCommand(rest);
        return;
      }

      if (t && t.trim()) micHeardText = true;
      if (res.isFinal) {
        lastResultCount = i + 1;
        finalTranscript += t + ' ';
        recogGotResult = true;
        updateTranscriptDisplay(finalTranscript.trim(), false);
        cmdInput.value = finalTranscript.trim();
        if (detectEndCommand(finalTranscript)) {
          addMsg('JARVIS_AI', 'Stop command detected. Processing...');
          finalizeVoice(true);
          return;
        }
        startSilenceTimer();
      } else {
        updateTranscriptDisplay((finalTranscript + t).trim(), false);
        cmdInput.value = (finalTranscript + t).trim();
        // Once a final result exists, trailing interim noise must not cancel
        // the pending auto-process timer (that is what stalled processing).
        if (!finalTranscript.trim()) resetSilenceTimer();
      }
    }
  };

  recog.onnomatch = () => {};

  // Restarting cannot fix these -- Chrome refuses again on every attempt, so
  // the session has to end rather than loop.
  const FATAL_STT = { 'not-allowed': 1, 'service-not-allowed': 1,
                      'audio-capture': 1, 'security': 1, 'network': 1 };

  recog.onerror = (e) => {
    const kind = (e && e.error) || 'unknown';
    if (kind === 'network' && getSttMode() === 'auto' && !fallbackStream) {
      addMsg('JARVIS_AI', 'Browser speech servers unreachable -- switching to JARVIS server mic.');
      voiceHalted = true; // stop onend resurrecting the recogniser we are dropping
      setTimeout(() => startFallbackRecord(), 300);
      return;
    }
    if (kind === 'aborted') return;
    if (kind === 'no-speech') return;
    const hints = {
      'not-allowed': MIC_BLOCKED_MSG,
      'service-not-allowed': MIC_BLOCKED_MSG,
      'audio-capture': 'No microphone found -- check your mic.',
      'network': 'Speech service unreachable -- check internet.',
    };
    const msg = hints[kind] || `Voice error (${kind})`;
    if (FATAL_STT[kind]) { haltVoiceOnError(msg); return; }
    warnVoiceOnce(msg);
    setListenLabel(msg, false);
    setTranscriptState('ERROR');
  };

  recog.onend = () => {
    recognizing = false;
    resetSilenceTimer();
    // onerror already ended this session: do not restart, and leave its
    // message standing instead of letting the IDLE reset below erase it.
    if (voiceHalted) {
      restoreCoreState(800);
      return;
    }
    if (voiceMode === 'listening') {
      // Standby survives Chrome's own stop/restart cycles.
      if (sessionKind === 'wake') {
        lastResultCount = 0;
        finalTranscript = '';
        micHeardText = false;
        try { recog.start(); } catch {}
        return;
      }
      const text = heardFromMic();
      if (text) {
        finalTranscript = text;
        finalizeVoice();
        return;
      }
      // Fresh session => e.results restarts empty; a stale lastResultCount
      // made every later result index out of range and get silently dropped.
      lastResultCount = 0;
      finalTranscript = '';
      micHeardText = false;
      try { recog.start(); } catch {}
      return;
    }
    btnMic.classList.remove('active');
    showVoiceControls(false);
    if (!recogGotResult && !finalTranscript.trim()) {
      setListenLabel('IDLE', false);
      setTranscriptState('IDLE');
    }
    restoreCoreState(800);
  };

  try {
    recog.start();
  } catch (err) {
    recognizing = false;
    voiceMode = 'idle';
    btnMic.classList.remove('active');
    showVoiceControls(false);
    addMsg('JARVIS_AI', `Could not start mic: ${err && err.message ? err.message : err}`);
    setListenLabel('IDLE', false);
    setTranscriptState('ERROR');
  }
  return true;
}

function stopWebSpeech() {
  try { recog.stop(); } catch {}
}

/* ============================================================
   WAV FALLBACK RECORDER (Server STT)
   ============================================================ */
async function startFallbackRecord() {
  if (fallbackStream) { stopFallbackRecord(true); return; }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    addMsg('JARVIS_AI', 'No mic API in this browser -- use Chrome/Edge or type instead.');
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    fallbackStream = { stream, chunks: [], ctx: null };
    const AC = window.AudioContext || window.webkitAudioContext;
    const ctx = new AC();
    await ctx.resume().catch(() => {});
    const src = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    const pcm = [];
    const inRate = ctx.sampleRate, wantRate = 16000;
    const startedAt = Date.now();
    proc.onaudioprocess = (e) => {
      const d = e.inputBuffer.getChannelData(0);
      const step = inRate / wantRate;
      let peak = 0;
      for (let i = 0; i < d.length; i += step) {
        const i0 = Math.floor(i), i1 = Math.min(d.length - 1, i0 + 1);
        const f = i - i0;
        pcm.push(d[i0] * (1 - f) + d[i1] * f);
        const a = pcm[pcm.length - 1] < 0 ? -pcm[pcm.length - 1] : pcm[pcm.length - 1];
        if (a > peak) peak = a;
      }
      const fb = fallbackStream;
      if (fb && peak >= VOICE_THRESHOLD) {
        fb.heardSpeech = true;
        fb.lastLoudAt = Date.now();
      }
    };
    src.connect(proc); proc.connect(ctx.destination);
    fallbackStream.stop = () => { try { proc.disconnect(); } catch {} try { src.disconnect(); } catch {} ctx.close().catch(() => {}); stream.getTracks().forEach(t => t.stop()); };
    fallbackStream.pcm = pcm;
    fallbackStream.ctx = ctx;
    fallbackStream.heardSpeech = false;
    fallbackStream.lastLoudAt = startedAt;
    // Auto-stop: transcribe and run the command as soon as you stop
    // speaking. Previously this mode never fired on its own, so a spoken
    // command sat unprocessed until STOP was clicked.
    fallbackStream.vadTimer = setInterval(() => {
      const fb = fallbackStream;
      if (!fb) return;
      if (voiceMode !== 'listening') { clearInterval(fb.vadTimer); return; }
      const now = Date.now();
      if (fb.heardSpeech && now - fb.lastLoudAt >= FALLBACK_SILENCE_MS) {
        addMsg('JARVIS_AI', 'Silence detected. Processing...');
        stopFallbackRecord(false);
      } else if (now - startedAt >= FALLBACK_MAX_MS) {
        addMsg('JARVIS_AI', 'Recording time limit reached. Processing...');
        stopFallbackRecord(false);
      }
    }, 250);
    stopVoiceWatchdog(); // fallback mode is driven by the VAD timer above
    voiceMode = 'listening';
    btnMic.classList.add('active');
    showVoiceControls(true);
    showTranscriptPanel(true);
    updateTranscriptDisplay('', false);
    setTranscriptState(sessionKind === 'wake' ? 'STANDBY' : 'RECORDING');
    setListenLabel(sessionKind === 'wake' ? 'STANDBY... SAY "HEY JARVIS"' : 'RECORDING... SPEAK NOW', true);
    setCoreState('listening');
    interruptIfNeeded();
  } catch (err) {
    const name = err && err.name;
    fallbackStream = null;
    // Same treatment as the browser recogniser: leaving voiceMode untouched
    // here left the HUD claiming RECORDING while no capture was running.
    haltVoiceOnError(name === 'NotAllowedError'
      ? MIC_BLOCKED_MSG
      : `Mic unavailable: ${err && err.message ? err.message : err}`);
  }
}

function encodeWav(samples, sampleRate) {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const wstr = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  wstr(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); wstr(8, 'WAVE');
  wstr(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true); wstr(36, 'data');
  v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return new Blob([buf], { type: 'audio/wav' });
}

async function stopFallbackRecord(cancelled, manual) {
  const fb = fallbackStream;
  fallbackStream = null;
  btnMic.classList.remove('active');
  showVoiceControls(false);
  if (!fb) return;
  if (fb.vadTimer) clearInterval(fb.vadTimer);
  fb.stop();
  voiceMode = 'finalizing';
  setListenLabel('TRANSCRIBING...', false);
  setTranscriptState('TRANSCRIBING');
  if (cancelled) {
    voiceMode = 'idle';
    updateTranscriptDisplay('', false);
    showTranscriptPanel(false);
    setListenLabel('IDLE', false);
    setTranscriptState('IDLE');
    restoreCoreState(800);
    return;
  }
  if (!fb.pcm.length) {
    addMsg('JARVIS_AI', 'No audio captured -- check your mic is plugged in and allowed, then try again.');
    voiceMode = 'idle';
    updateTranscriptDisplay('', false);
    showTranscriptPanel(false);
    setListenLabel('IDLE', false);
    setTranscriptState('IDLE');
    restoreCoreState(800);
    return;
  }
  try {
    const wav = encodeWav(fb.pcm, 16000);
    addMsg('JARVIS_SYS', 'Server transcription: sending mic audio to the Google speech service.', 'sys');
    const r = await fetch(API_BASE + '/api/transcribe', { method: 'POST', body: wav });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
    const heard = (j.text || '').trim();
    // Standby: only an utterance carrying the wake word becomes a command.
    let cmd = heard;
    if (sessionKind === 'wake') {
      const rest = extractWake(heard);
      cmd = rest === null ? '' : rest;
    }
    if (cmd) {
      updateTranscriptDisplay(cmd, true);
      addMsg('JARVIS_AI', `Heard: "${cmd}"`);
      await handleCommand(cmd);
    } else {
      updateTranscriptDisplay('', false);
    }
  } catch (err) {
    const msg = err.message || String(err);
    if (msg.includes('could not understand')) {
      addMsg('JARVIS_AI', 'Audio recorded but speech not recognized -- speak louder/closer to mic, or type instead.');
    } else if (msg.includes('not installed')) {
      addMsg('JARVIS_AI', 'Server STT not installed -- run: pip install SpeechRecognition pyaudio');
    } else if (msg.includes('speech service error')) {
      addMsg('JARVIS_AI', 'Google speech service unreachable -- check internet, or type instead.');
    } else {
      addMsg('JARVIS_AI', `Transcription failed: ${msg} -- type instead.`);
    }
    setTranscriptState('ERROR');
  }
  voiceMode = 'idle';
  updateTranscriptDisplay('', false);
  showTranscriptPanel(false);
  setListenLabel('IDLE', false);
  setTranscriptState('IDLE');
  restoreCoreState(800);
  // manual == you pressed the mic/STOP yourself, so stay down.
  if (!manual) resumeAfterAnswer();
}

/* ============================================================
   VOICE FINALIZE (unified for Web Speech and WAV fallback)
   ============================================================ */
// manual=true  -> you stopped it yourself (mic click, STOP button): stay idle.
// manual=false -> it stopped on its own (silence, watchdog, wake session),
//                 so the assist loop can pick the conversation back up.
async function finalizeVoice(manual) {
  if (voiceMode !== 'listening') return; // idempotent: never run a command twice
  voiceMode = 'finalizing';
  resetSilenceTimer();
  stopVoiceWatchdog();
  setTranscriptState('PROCESSING');
  setListenLabel('PROCESSING...', false);

  if (fallbackStream) {
    stopFallbackRecord(false, manual);
    return;
  }

  if (recognizing) {
    // Detach before waiting on the reply: otherwise a late onresult lands
    // while sessionKind is still 'command' with lastResultCount reset to 0,
    // and re-appends every earlier result from index 0.
    if (recog) recog.onresult = recog.onend = recog.onerror = recog.onnomatch = null;
    try { recog.stop(); } catch {}
    recognizing = false;
  }

  const text = heardFromMic();
  finalTranscript = '';
  lastResultCount = 0;
  micHeardText = false;

  // Sign-off phrases steer the voice loop itself, so they are handled BEFORE
  // dispatch. Routed as real commands they misfire badly: "bye" is an alias
  // for `shutdown` (kills the HUD) and "go to sleep" runs `navigate`.
  const signingOff = !!(text && assistMode !== 'off' && ASSIST_EXIT_RE.test(text.trim()));

  if (text) {
    updateTranscriptDisplay(text, true);
    if (signingOff) {
      addMsg('JARVIS_AI', 'Standing down.');
    } else {
      addMsg('JARVIS_AI', `Heard: "${text}"`);
      await handleCommand(text);
    }
  } else {
    updateTranscriptDisplay('', false);
  }

  if (signingOff) {
    setAssistMode('off');
    manual = true;
  }

  voiceMode = 'idle';
  sessionKind = 'manual';
  btnMic.classList.remove('active');
  showVoiceControls(false);
  showTranscriptPanel(false);
  setListenLabel('IDLE', false);
  setTranscriptState('IDLE');
  cmdInput.value = '';
  restoreCoreState(800);
  if (!manual) resumeAfterAnswer();
}

/* ============================================================
   VOICE CONTROLS
   ============================================================ */
function toggleMic() {
  clearTimeout(resumeTimer);
  if (voiceMode === 'listening') {
    finalizeVoice(true);
    return;
  }
  startListening('command');
}

function stopVoice() {
  if (voiceMode !== 'listening') return;
  finalizeVoice(true);
}

function cancelVoice() {
  if (voiceMode !== 'listening') return;
  if (fallbackStream) {
    stopFallbackRecord(true);
    return;
  }
  if (recognizing) {
    try { recog.stop(); } catch {}
  }
  voiceMode = 'idle';
  sessionKind = 'manual';
  clearTimeout(resumeTimer);
  finalTranscript = '';
  lastResultCount = 0;
  micHeardText = false;
  resetSilenceTimer();
  stopVoiceWatchdog();
  btnMic.classList.remove('active');
  showVoiceControls(false);
  showTranscriptPanel(false);
  updateTranscriptDisplay('', false);
  setListenLabel('IDLE', false);
  setTranscriptState('IDLE');
  cmdInput.value = '';
  restoreCoreState(800);
}

/* --- STT mode cycling --- */
function getSttMode() {
  try { return localStorage.getItem('jarvis_stt') || 'auto'; }
  catch { return 'auto'; }
}
function cycleSttMode(ev) {
  if (ev) ev.preventDefault();
  const order = ['auto', 'browser', 'server'];
  let cur = 'auto';
  try { cur = localStorage.getItem('jarvis_stt') || 'auto'; } catch {}
  const next = order[(order.indexOf(cur) + 1) % order.length];
  try { localStorage.setItem('jarvis_stt', next); } catch {}
  addMsg('JARVIS_AI', `Mic mode: ${next.toUpperCase()} -- ` + (
    next === 'server' ? 'server transcribes via the Google speech service (mic audio leaves this PC).' :
    next === 'browser' ? 'browser speech recognition only (Chrome sends mic audio to Google).' :
    'browser first, server fallback on failure (both use the Google speech service). (Recommended)'));
  return false;
}

/* --- Event bindings --- */
btnMic.onclick = toggleMic;
btnMic.oncontextmenu = cycleSttMode;
btnMic.title = 'Voice input (click to start/stop)';
if (btnStop) btnStop.onclick = stopVoice;
if (btnCancel) btnCancel.onclick = cancelVoice;

const btnAssist = document.getElementById('btnAssist');
if (btnAssist) btnAssist.onclick = cycleAssistMode;
// Restore the hands-free mode you left it on.
try {
  const saved = localStorage.getItem('jarvis_assist');
  if (saved === 'conversation' || saved === 'standby') {
    setAssistMode(saved);
    if (saved === 'standby') startWakeSession();
  }
} catch {}
renderAssistBtn();

// Report a blocked mic up front. Without this, hands-free looks armed while
// every attempt dies in silence -- which reads as "assist is broken".
(function probeMicPermission() {
  try {
    if (!navigator.permissions || !navigator.permissions.query) return;
    navigator.permissions.query({ name: 'microphone' }).then((st) => {
      const announce = () => { if (st.state === 'denied') warnVoiceOnce(MIC_BLOCKED_MSG); };
      announce();
      try {
        st.onchange = () => {
          if (st.state === 'denied') warnVoiceOnce(MIC_BLOCKED_MSG);
          else if (st.state === 'granted') addMsg('JARVIS_AI', 'Microphone allowed -- voice is ready.');
        };
      } catch {}
    }).catch(() => {});
  } catch {}
})();

/* ============================================================
   REACTOR RENDER LOOP
   ============================================================ */
(function () {
  const SVGNS = 'http://www.w3.org/2000/svg';
  function buildTicks(id, count, rOut, rMin, rMaj, majorEvery, color, wMin, wMaj) {
    const svg = document.getElementById(id);
    if (!svg) return;
    for (let i = 0; i < count; i++) {
      const a = (i / count) * Math.PI * 2;
      const major = i % majorEvery === 0;
      const r1 = major ? rMaj : rMin;
      const l = document.createElementNS(SVGNS, 'line');
      l.setAttribute('x1', 200 + rOut * Math.cos(a)); l.setAttribute('y1', 200 + rOut * Math.sin(a));
      l.setAttribute('x2', 200 + r1 * Math.cos(a)); l.setAttribute('y2', 200 + r1 * Math.sin(a));
      l.setAttribute('stroke', color); l.setAttribute('stroke-width', major ? wMaj : wMin);
      l.setAttribute('opacity', major ? '0.9' : '0.45');
      svg.appendChild(l);
    }
  }
  buildTicks('tickOuter', 120, 197, 188, 181, 10, '#35e0ff', 1, 2);
  buildTicks('tickInner', 60, 179, 173, 168, 5, '#7df3ff', 1, 1.6);

  const cv = document.getElementById('particleCore');
  const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height, CX = W / 2, CY = H / 2;
  const N = 650, R = 72;
  const pts = [];
  for (let i = 0; i < N; i++) {
    const k = i + 0.5;
    pts.push({ phi: Math.acos(1 - 2 * k / N), theta: Math.PI * (1 + Math.sqrt(5)) * k });
  }
  let rot = 0;
  function drawHeart() {
    ctx.clearRect(0, 0, W, H);
    rot += 0.004;
    const g = ctx.createRadialGradient(CX, CY, 4, CX, CY, 110);
    g.addColorStop(0, 'rgba(125,243,255,.35)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    for (const p of pts) {
      const th = p.theta + rot;
      const x = R * Math.sin(p.phi) * Math.cos(th);
      const y = R * Math.cos(p.phi);
      const z = R * Math.sin(p.phi) * Math.sin(th);
      const depth = (z + R) / (2 * R);
      ctx.fillStyle = `rgba(140,235,255,${(0.15 + depth * 0.85).toFixed(2)})`;
      ctx.beginPath(); ctx.arc(CX + x, CY + y, 0.5 + depth * 1.5, 0, Math.PI * 2); ctx.fill();
    }
  }

  const wv = document.getElementById('waveForm');
  const wctx = wv.getContext('2d');
  let level = 0.15, t = 0;
  function sizeWave() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = wv.clientWidth || 300, h = 54;
    if (wv.width !== w * dpr) { wv.width = w * dpr; wv.height = h * dpr; }
    wctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener('resize', sizeWave); sizeWave();
  function voiceTarget() {
    if (fallbackStream || recognizing) return 0.9;
    if (voiceOutActive || (window.speechSynthesis && speechSynthesis.speaking)) return 0.65;
    if (coreMode === 'thinking' || coreMode === 'responding') return 0.45;
    return 0.14;
  }
  function drawWave() {
    sizeWave();
    const w = wv.clientWidth || 300, h = 54, mid = h / 2;
    level += (voiceTarget() - level) * 0.08;
    t += 0.12;
    wctx.clearRect(0, 0, w, h);
    wctx.strokeStyle = 'rgba(53,224,255,.25)';
    wctx.beginPath(); wctx.moveTo(0, mid); wctx.lineTo(w, mid); wctx.stroke();
    const bars = 72, bw = w / bars;
    for (let i = 0; i < bars; i++) {
      const env = Math.sin((i / bars) * Math.PI);
      const v = Math.abs(Math.sin(i * 0.55 + t) * 0.6 + Math.sin(i * 0.21 - t * 1.7) * 0.4);
      const bh = Math.max(2, v * level * env * h * 0.92);
      const hot = level > 0.4;
      wctx.fillStyle = hot ? 'rgba(125,255,212,.9)' : 'rgba(53,224,255,.75)';
      wctx.shadowColor = hot ? '#7dffd4' : '#35e0ff'; wctx.shadowBlur = 6;
      wctx.fillRect(i * bw + bw * 0.22, mid - bh / 2, bw * 0.56, bh);
    }
    wctx.shadowBlur = 0;
  }
  (function loop() { drawHeart(); drawWave(); requestAnimationFrame(loop); })();
})();
