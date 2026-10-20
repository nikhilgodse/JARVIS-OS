"""Voice output (TTS) and microphone input.

Engine priority: pyttsx3 if installed, else zero-dependency native TTS
(Windows SAPI via PowerShell, macOS `say`, Linux `spd-say`/`espeak`).
Nothing here requires a pip install.
"""

import shutil
import subprocess
import sys
import threading

from . import speaker
from ..utils import storage

try:
    _voice_enabled = bool(storage.load("config", {}).get("voice_enabled", False))
except Exception:
    _voice_enabled = False
_engine = None
_engine_lock = threading.Lock()


def voice_enabled():
    return _voice_enabled


def set_voice_enabled(on):
    global _voice_enabled
    _voice_enabled = bool(on)
    try:
        cfg = storage.load("config", {})
        if isinstance(cfg, dict):
            cfg["voice_enabled"] = _voice_enabled
            storage.save("config", cfg)
    except Exception:
        pass


def native_tts_platform():
    """Name of the native TTS backend for this OS, or None if unknown."""
    if sys.platform == "win32":
        return "sapi"
    if sys.platform == "darwin":
        return "say"
    if sys.platform.startswith("linux"):
        if shutil.which("spd-say"):
            return "spd-say"
        if shutil.which("espeak"):
            return "espeak"
        return None
    return None


def _get_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            try:
                import pyttsx3
            except ImportError:
                return None
            try:
                _engine = pyttsx3.init()
            except Exception:
                return None
        return _engine


def _speak_native(text):
    """Blocking native speech. Returns True if a backend was attempted."""
    plat = native_tts_platform()
    try:
        if plat == "sapi":
            # Use double quotes and escape for PowerShell
            safe = text.replace('"', '`"')
            cmd = f'(New-Object -ComObject SAPI.SpVoice).Speak("{safe}")'
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=60)
            return True
        if plat == "say":
            subprocess.Popen(["say", text],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if plat in ("spd-say", "espeak"):
            subprocess.Popen([plat, text],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception:
        pass
    return False


def speak(text):
    """Vocalise text in the background. pyttsx3 preferred, native fallback."""
    if not text:
        return
    eng = _get_engine()
    if eng is not None:
        def _run_pyttsx3():
            try:
                with _engine_lock:
                    eng.say(text)
                    eng.runAndWait()
            except Exception:
                pass

        threading.Thread(target=_run_pyttsx3, daemon=True).start()
        return

    def _run_native():
        _speak_native(text)

    threading.Thread(target=_run_native, daemon=True).start()


def listen_once(timeout=6):
    """Capture one utterance from the mic. Returns text or an error string."""
    try:
        import speech_recognition as sr
    except ImportError:
        return None, "server STT not installed (pip install SpeechRecognition pyaudio)"
    r = sr.Recognizer()
    try:
        with sr.Microphone() as src:
            r.adjust_for_ambient_noise(src, duration=0.5)
            audio = r.listen(src, timeout=timeout, phrase_time_limit=12)
        return r.recognize_google(audio), ""
    except Exception as e:
        return None, f"mic capture failed: {e}"
