import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.core import parser, speaker, auth, voice
from jarvis.modules.files import FileManager
from jarvis.modules import system, scheduler, launcher, llm, pccontrol, apps
from jarvis.modules.chat import ChatBrain
from jarvis.skills import files as files_skill
from jarvis.skills import confirm as confirm_skill
from jarvis.utils import storage
from jarvis import skills


class Router:
    def __init__(self):
        self.fm = FileManager()
        self.chat = ChatBrain()
        self.scheduler = None
        skills.timers.set_spoken_cb(lambda msg: self.chat_say(msg))

    def bind_scheduler(self, sched):
        self.scheduler = sched

    def chat_say(self, text):
        speaker.say(text)

    def _ctx(self):
        cfg = storage.load("config", {})
        return {"cwd": self.fm.cwd, "user": "sir", "location": cfg.get("location") or None}

    def _say(self, text):
        speaker.say(text)
        if voice.voice_enabled():
            voice.speak(text)

    def voice_enabled(self):
        return voice.voice_enabled()

    def run(self, text, silent: bool = False):
        # First check for high-confidence WhatsApp intents
        # This must happen BEFORE command parsing to prevent routing to web search
        from .skills import whatsapp as whatsapp_skill
        whatsapp_intent = whatsapp_skill.detect_intent(text)
        if whatsapp_intent and whatsapp_intent.get("confidence", 0) >= 0.7:
            skill_reply = skills.handle(text, self._ctx())
            if skill_reply:
                if not silent:
                    speaker.say(skill_reply)
                return
        
        parsed = parser.parse(text)
        command = parsed["command"]
        args = parsed["args"]
        arg_str = " ".join(args)
        implicit = parsed["implicit"]

        try:
            if command is None:
                return
            if command == "help":
                parser.help_text()
            elif command == "status":
                if not silent:
                    speaker.say("Fetching system snapshot...")
                system.show(system.get_snapshot())
            elif command == "scan":
                if not silent:
                    speaker.say("Scanning processes...")
                system.show_processes(15)
            elif command == "open":
                if not args:
                    launcher.known_apps()
                else:
                    folder_reply = files_skill.open_folder_arg(arg_str)
                    if folder_reply:
                        speaker.say(folder_reply)
                        return
                    local_reply = files_skill.open_local_target(arg_str, self.fm.cwd)
                    if local_reply:
                        speaker.say(local_reply)
                        return
                    opener_reply = skills.opener.launch_target(arg_str)
                    if opener_reply:
                        speaker.say(opener_reply)
                    else:
                        # Verified launch: honest result, never a blind success.
                        r = apps.launch_app(arg_str)
                        if r["ok"]:
                            speaker.success_msg(f"{r['launched']} is open.")
                        else:
                            speaker.error_msg(r["error"])
            elif command == "list":
                self.fm.list()
            elif command == "navigate":
                self.fm.navigate(" ".join(args))
            elif command == "create":
                if not args:
                    speaker.error_msg("Usage: create <name>[/]")
                else:
                    m = re.match(r"^(?:a\s+)?(?:new\s+)?(?:folder|directory)\s+(?:called\s+|named\s+)?(.+)$",
                                 arg_str, re.IGNORECASE)
                    if m and m.group(1).strip():
                        self.fm.create(m.group(1).strip(), kind="dir")
                    else:
                        m2 = re.match(r"^(?:a\s+)?(?:new\s+)?file\s+(?:called\s+|named\s+)?(.+)$",
                                      arg_str, re.IGNORECASE)
                        if m2 and m2.group(1).strip():
                            self.fm.create(m2.group(1).strip())
                        else:
                            self.fm.create(args[0])
            elif command == "remove":
                if not args:
                    speaker.error_msg("Usage: remove <name>")
                else:
                    # Destructive: resolve exactly, then two-step confirmation.
                    target = " ".join(args)
                    resolved, err = files_skill.resolve_delete(target, self.fm.cwd)
                    if err:
                        speaker.error_msg(err)
                    else:
                        speaker.line(confirm_skill.request(
                            "delete", f"Delete '{resolved}'?",
                            {"path": resolved, "cwd": self.fm.cwd}))
            elif command == "copy":
                if "clipboard" in arg_str.lower():
                    content = arg_str.lower().replace("copy ", "", 1).replace(" to clipboard", "").strip().strip("?.")
                    if content:
                        pccontrol.clipboard_set(content)
                        speaker.success_msg(f"Copied '{content}' to clipboard.")
                    else:
                        self.fm.copy(args[0] if args else "", args[1] if len(args) > 1 else "")
                else:
                    self.fm.copy(args[0] if args else "", args[1] if len(args) > 1 else "")
            elif command == "move":
                self.fm.move(args[0] if args else "", args[1] if len(args) > 1 else "")
            elif command == "search":
                if not args and not implicit:
                    speaker.error_msg("Usage: search <pattern>")
                else:
                    q = arg_str
                    freply = files_skill.find_files_reply(q, self.fm.cwd)
                    if freply:
                        speaker.say(freply)
                    elif q.lower().startswith(("the web", "web for", "internet")):
                        speaker.say(skills.websearch.handler("search " + q, self._ctx())
                                    or "Web search had nothing.")
                    else:
                        if q.lower().startswith("for "):
                            q = "search " + q
                        sreply = skills.opener.handler(q, self._ctx())
                        if sreply:
                            speaker.say(sreply)
                        else:
                            self.fm.search(q)
            elif command == "automate":
                if not args:
                    speaker.error_msg("Usage: automate <seconds> <command>")
                elif not self.scheduler:
                    speaker.error_msg("Scheduler is not available in this session.")
                else:
                    self.scheduler.schedule(args[0], " ".join(args[1:]))
            elif command == "jobs":
                if not self.scheduler:
                    speaker.error_msg("Scheduler is not available in this session.")
                elif args and args[0].lower() == "cancel":
                    self.scheduler.cancel(args[1] if len(args) > 1 else "")
                else:
                    self.scheduler.list()
            elif command == "authenticate":
                self._login(" ".join(args) if args else None)
            elif command == "chat":
                if not args and not implicit:
                    self._chat_loop()
                else:
                    self._chat_respond(parsed["raw"] if implicit else arg_str)
            elif command == "pc":
                if not args:
                    speaker.line("Syntax: pc <verb> [args]. Try: pc doctor, pc volume, pc screenshot, pc ip")
                else:
                    _, pc_lines = pccontrol.run_verbs(args)
                    for ln in pc_lines:
                        speaker.line(ln)
            elif command == "speak":
                if not args:
                    speaker.error_msg("Usage: speak <text>")
                else:
                    voice.speak(arg_str)
            elif command == "voice":
                toggle = args[0].lower() if args else ""
                if toggle in ("on", "enable"):
                    voice.set_voice_enabled(True)
                    speaker.success_msg("Voice output enabled. Jarvis will speak replies.")
                elif toggle in ("off", "disable"):
                    voice.set_voice_enabled(False)
                    speaker.success_msg("Voice output disabled.")
                else:
                    self._voice_loop()
            elif command == "brain":
                if args and args[0].lower() == "set":
                    self._set_llm(args[1:])
                else:
                    self._brain()
            elif command == "skills":
                self._show_skills()
            elif command == "doctor":
                speaker.header("DIAGNOSTIC REPORT")
                # System health
                snap = system.get_snapshot()
                cpu = snap.get("cpu_load")
                mem = snap.get("used_mem")
                mem_total = snap.get("total_mem")
                mem_pct = round(mem / mem_total * 100, 1) if mem and mem_total else "?"
                speaker.line(f"System: CPU {cpu}% | RAM {mem_pct}%")
                # Provider health
                try:
                    speaker.line(llm.doctor())
                except Exception as e:
                    speaker.error_msg(f"LLM diagnostic failed: {e}")
            elif command == "location":
                self._set_location(args)
            elif command == "reset":
                self.chat.reset()
            elif command == "clear":
                if sys.platform == "win32":
                    os.system("cls")
                else:
                    os.system("clear")
            elif command == "shutdown":
                speaker.say("Goodbye, sir. Shutting down gracefully.")
                sys.exit(0)
            else:
                if not implicit:
                    speaker.error_msg(f'Unknown command: "{command}". Type "help" for options.')
        except Exception as e:
            speaker.error_msg(str(e))

    def _login(self, password=None):
        if not auth.is_configured():
            speaker.say("First run. Registering master password.")
            auth.register(os.environ.get("JARVIS_MASTER_PASSWORD") or auth.DEFAULT_PASSWORD)
        if password is None:
            password = auth.prompt_hidden("Password (default: jarvis): ")
        if not password:
            password = auth.DEFAULT_PASSWORD
        if auth.authenticate(password):
            speaker.success_msg("Access granted. Welcome, sir.")
        else:
            speaker.error_msg("Access denied.")

    def _chat_respond(self, text):
        try:
            speaker.say(self.chat.reply(text, self._ctx()))
        except Exception as e:
            speaker.error_msg(str(e))

    def _chat_loop(self):
        speaker.line('Chat mode. Type "exit" to leave.')
        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                speaker.line("Leaving chat mode.")
                return
            if line.lower() in ("exit", "quit", "back"):
                return
            if line:
                self._chat_respond(line)

    def _voice_loop(self):
        speaker.line('Voice mode. Say "stop listening" (or press Ctrl+C) to leave.')
        while True:
            try:
                text, err = voice.listen_once(timeout=8)
            except KeyboardInterrupt:
                speaker.line("Leaving voice mode.")
                return
            if err and not text:
                speaker.warn_msg(err)
                continue
            if not text:
                continue
            speaker.line(f'Heard: "{text}"')
            if text.lower().strip() in ("stop listening", "stop", "exit voice"):
                return
            self.run(text)

    def _brain(self):
        s = llm.settings()
        speaker.header("LLM BRAIN")
        speaker.line(f"Configured: {'yes' if llm.is_configured() else 'no'}")
        speaker.line(f"Model: {s.get('model')}")
        speaker.line(f"Endpoint: {s.get('endpoint')}")
        key = s.get("api_key") or ""
        speaker.line(f"API key: {'*' * 8 + key[-4:] if len(key) > 4 else ('set' if key else 'not set')}")
        speaker.line("Set with: brain set key|endpoint|model <value>")

    def _set_llm(self, args):
        if len(args) < 2:
            speaker.error_msg("Usage: brain set key|endpoint|model <value>")
            return
        field, value = args[0].lower(), " ".join(args[1:])
        if field in ("key", "api_key", "api-key"):
            llm.set_config(api_key=value)
        elif field == "endpoint":
            llm.set_config(endpoint=value)
        elif field == "model":
            llm.set_config(model=value)
        else:
            speaker.error_msg("Usage: brain set key|endpoint|model <value>")
            return
        speaker.success_msg("Brain configuration updated.")

    def _show_skills(self):
        speaker.header("SKILLS")
        for name, desc in skills.list_skills():
            speaker.raw(f"  {speaker.CYAN}{speaker.BOLD}{name.ljust(12)}{speaker.RESET}{speaker.GRAY}{desc}{speaker.RESET}")

    def _set_location(self, args):
        if not args:
            cfg = storage.load("config", {})
            speaker.line(f"Home city: {cfg.get('location') or '(not set)'}. Usage: location <city>")
            return
        cfg = storage.load("config", {})
        cfg["location"] = " ".join(args)
        storage.save("config", cfg)
        speaker.success_msg(f"Home city set to {cfg['location']}.")


def main():
    router = Router()
    sched = scheduler.Scheduler(router)
    router.bind_scheduler(sched)
    speaker.header("JARVIS OS")
    speaker.line('Type "help" for commands, "shutdown" to power down.')
    while True:
        try:
            line = input("jarvis> ")
        except (EOFError, KeyboardInterrupt):
            speaker.say("Goodbye, sir.")
            return
        if not line.strip():
            continue
        try:
            router.run(line)
        except SystemExit:
            raise
        except Exception as e:
            speaker.error_msg(str(e))


if __name__ == "__main__":
    main()
