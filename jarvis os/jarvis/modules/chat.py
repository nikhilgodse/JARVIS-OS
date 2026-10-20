import re
from datetime import datetime

from ..core import speaker
from .. import skills
from . import llm

# Action verbs that can follow a greeting ("hey play X"). When _local sees
# one of these after hi/hello/hey, it returns "" so the skills route the
# command instead of answering the greeting.
_GREET_THEN_CMD_RE = re.compile(
    r"^(?:play|playing|put\s+on|watch|open|launch|start|search|find|tell|"
    r"send|message|text|set|stop|pause|resume|turn|remind|timer|note|"
    r"remember|weather|call)\b")


class ChatBrain:
    """Conversational brain: uses the configured LLM when available,
    otherwise falls back to local deterministic replies."""

    def __init__(self, max_history: int = 12):
        self.local_responses = {
            ("hi", "hello", "hey", "good morning", "howdy"): "What do you need.",
            ("bye", "goodbye", "see you", "farewell"): "Later.",
            ("thank", "thx", "good job", "nice"): "Yeah, no problem.",
            "who are you": "JARVIS. I run this machine -- system, files, tasks, and whatever you ask me.",
            "how are you": "All good. Systems nominal.",
        }
        self.max_history = max_history
        self.history = []

    def reply(self, text: str, ctx: dict) -> str:
        """Get a reply for user text. Returns the reply string."""
        # Deterministic replies (identity, greetings, time) answer the same
        # way on turn 1 and turn 20. They used to be skipped once the
        # conversation had history, so "who are you" fell through to the
        # wikipedia skill and came back with a dictionary definition.
        local = self._local(text, ctx)
        if local:
            return local

        skill_reply = skills.handle(text, ctx)
        if skill_reply:
            self.history = []
            return skill_reply

        self.history.append({"role": "user", "content": text})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        if llm.is_configured():
            try:
                reply = llm.complete(self.history)
                self.history.append({"role": "assistant", "content": reply})
                return reply
            except RuntimeError as e:
                speaker.warn_msg(str(e))
                self.history.pop()
                return self._fallback(text, ctx, configured=True)

        self.history.clear()
        return self._fallback(text, ctx, configured=False)

    def reset(self):
        self.history = []
        speaker.success_msg("Conversation context cleared.")

    def _local(self, text: str, ctx: dict) -> str:
        lower = text.lower().strip()

        # A greeting that introduces a real command ("hey play despacito",
        # "hello open youtube") must not swallow it: voice input starts
        # with hey/hi/hello constantly, so an action verb after the
        # greeting bails out to the skills. Bare greetings reply as before.
        if lower in ("hi", "hello", "hey") or lower.startswith(
            ("hi ", "hello ", "hey ", "good morning", "good afternoon", "good evening", "good day")
        ):
            rest = re.sub(
                r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening|day))\b[,\s]*",
                "", lower).strip()
            if rest and _GREET_THEN_CMD_RE.match(rest):
                return ""
            return self.local_responses[("hi", "hello", "hey", "good morning", "howdy")]
        if any(g in lower for g in ("bye", "goodbye", "see you", "farewell")):
            return self.local_responses[("bye", "goodbye", "see you", "farewell")]
        if any(t in lower for t in ("thank", "thx", "good job", "nice")):
            return self.local_responses[("thank", "thx", "good job", "nice")]
        if "who are you" in lower:
            return self.local_responses["who are you"]
        if "how are you" in lower or lower == "status":
            return self.local_responses["how are you"]

        # Questions about JARVIS himself. He has no encyclopedia entry, but
        # Wikipedia answers anyway: "what is your name" returned the film
        # *Your Name*, and "what is your purpose" a church in the Philippines.
        # A full match keeps this to the bare question, so something like
        # "tell me about your name of this file" still reaches the LLM --
        # which is protected from Wikipedia by the same pattern there.
        m_self = re.fullmatch(
            r"(?:what(?:'s| is| are)?|who(?:'s| is| are)?|whose|tell\s+me(?:\s+about)?)\s+"
            r"your\s+(name|age|purpose|identity|creator|maker|birthday)"
            r"(?:\s+(?:please|jarvis|in\s+life))?\s*[?!.\s]*", lower)
        if m_self:
            noun = m_self.group(1)
            if noun == "age":
                return "No age. I was installed, not born."
            if noun == "purpose":
                return "Run this machine and answer you. That's it."
            if noun in ("creator", "maker"):
                return "You built me."
            return "JARVIS."
        if "what should i call you" in lower or lower == "who should i call you":
            return "JARVIS."

        # System-related questions -> route to system skill
        if re.search(r"\b(status|specs|specifications|hardware|battery|ram|cpu|disk|uptime)\b", lower):
            if re.search(r"\b(my|the|this|your|laptop|computer|pc|system|device)\b", lower):
                return None  # Let skills.handle() route to system skill

        # Instant factual replies stay local even when an LLM is attached.
        if re.search(r"\b(what time|current time|the time)\b", lower):
            return f"The current time is {datetime.now().strftime('%H:%M:%S')}."
        if "today's date" in lower or "what date" in lower or "what day" in lower:
            return f"Today's date is {datetime.now().strftime('%Y-%m-%d')}."
        if "where am i" in lower or "directory" in lower or "cwd" in lower:
            return f"You are currently in: {ctx.get('cwd') or ''}"
        if "help" in lower or "what can you do" in lower:
            return ("I can monitor system status, scan processes, manage files, "
                    "launch applications, schedule automated tasks, and hold conversations. "
                    "Type 'help' for the full command list.")
        return ""

    def _fallback(self, text: str, ctx: dict, configured: bool = False) -> str:
        if configured:
            return "Apologies, the brain is unreachable at the moment. Please try again."
        return ("I'm running in offline mode. No LLM API is configured. "
                "Set JARVIS_LLM_API_KEY (or an OpenAI-compatible endpoint) to unlock my full brain, "
                "or use 'brain' to see setup options.")
