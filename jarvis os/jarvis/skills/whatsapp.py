"""WhatsApp messaging skill with structured intent detection.

Provides:
- Intent detection for WhatsApp commands
- Structured intent output
- NL message parsing
- UI automation for WhatsApp Web/Desktop
"""

import re
import time
from . import confirm
from ..modules import pccontrol, apps

# ---------------------------------------------------------------------------
# Intent detection - structured output
# ---------------------------------------------------------------------------

# Intent types
INTENT_WHATSAPP_OPEN = "whatsapp.open"
INTENT_WHATSAPP_SEND = "whatsapp.send_message"
INTENT_WHATSAPP_SEARCH = "whatsapp.search_chat"
INTENT_WHATSAPP_READ = "whatsapp.read_message"

# Confidence thresholds
HIGH_CONFIDENCE = 0.9
MEDIUM_CONFIDENCE = 0.7
LOW_CONFIDENCE = 0.5


def detect_intent(text):
    """Detect WhatsApp intent from user text.
    
    Returns a structured intent dict or None:
    {
        "intent": "whatsapp.send_message",
        "application": "whatsapp",
        "recipient": "Shreyash",
        "message": "Hi",
        "confidence": 0.9
    }
    """
    lower = text.lower().strip()
    
    # Check for explicit web search request - should NOT be routed to WhatsApp
    # "search google for WhatsApp" should be web search, not WhatsApp
    web_search_explicit = (
        r"^search\s+(?:google|the\s+web|the\s+internet)\s+for\s+",
        r"^google\s+search\s+",
        r"^web\s+search\s+",
    )
    for pattern in web_search_explicit:
        if re.match(pattern, lower):
            return None
    
    # Extract WhatsApp context
    has_whatsapp = any(w in lower for w in ("whatsapp", "whats app", "wa "))
    
    # Handle compound commands: "open whatsapp and send X to Y"
    compound_match = re.match(
        r"^(?:open|launch|start)\s+whatsapp\s+(?:and|then)\s+(.+?)$",
        lower
    )
    if compound_match:
        rest = compound_match.group(1)
        # Try to detect send intent from the rest
        send_intent = _detect_send_intent(rest, rest, has_whatsapp)
        if send_intent:
            return send_intent
    
    # Intent 1: Open WhatsApp (must be before search patterns)
    # Only match if there's no "and send/message" after whatsapp
    open_patterns = (
        r"^(?:open|launch|start|show|go to)\s+(?:the\s+)?(?:my\s+)?whatsapp(?:\s+(?:web|desktop|app))?\s*$",
        r"^whatsapp(?:\s+(?:web|desktop|app))?\s*$",
    )
    for pattern in open_patterns:
        if re.match(pattern, lower):
            # Make sure there's no "and send/message" after
            if not re.search(r"\b(?:and|then)\s+(?:send|message|text|tell)\b", lower):
                return {
                    "intent": INTENT_WHATSAPP_OPEN,
                    "application": "whatsapp",
                    "recipient": None,
                    "message": None,
                    "confidence": HIGH_CONFIDENCE
                }
    
    # Intent 2: Search chat (only for explicit search/find commands)
    search_patterns = (
        r"^(?:find|search)\s+(.+?)(?:'s)?\s+(?:on\s+)?(?:whatsapp|chat|conversation)",
        r"^(?:find|search)\s+(?:the\s+)?(?:whatsapp|chat|conversation)\s+(?:with\s+)?(.+?)$",
        r"^(?:whatsapp|chat|conversation)\s+(?:search|find)\s+(.+?)$",
    )
    for pattern in search_patterns:
        m = re.search(pattern, lower)
        if m:
            recipient = _clean_name(m.group(1))
            if recipient:
                return {
                    "intent": INTENT_WHATSAPP_SEARCH,
                    "application": "whatsapp",
                    "recipient": recipient,
                    "message": None,
                    "confidence": HIGH_CONFIDENCE if has_whatsapp else MEDIUM_CONFIDENCE
                }
    
    # Intent 3: Send message - complex patterns
    send_intent = _detect_send_intent(text, lower, has_whatsapp)
    if send_intent:
        return send_intent
    
    # Intent 4: If WhatsApp is mentioned but no specific intent detected
    # Could be a general WhatsApp query - route to WhatsApp skill for handling
    if has_whatsapp:
        # Check if there's a message-like pattern
        msg_patterns = (
            r"(?:send|message|text|tell|msg|ping|forward|write)\s+",
        )
        has_msg_action = any(re.search(p, lower) for p in msg_patterns)
        
        if has_msg_action:
            # Has message action but didn't match send patterns above
            # Try to extract recipient and message
            parsed = _parse_command(text)
            if parsed[0]:  # Has recipient
                return {
                    "intent": INTENT_WHATSAPP_SEND,
                    "application": "whatsapp",
                    "recipient": parsed[0],
                    "message": parsed[1] or "",
                    "confidence": MEDIUM_CONFIDENCE
                }
        
        # Just "whatsapp" mentioned - return open intent
        return {
            "intent": INTENT_WHATSAPP_OPEN,
            "application": "whatsapp",
            "recipient": None,
            "message": None,
            "confidence": LOW_CONFIDENCE
        }
    
    return None


def _detect_send_intent(text, lower, has_whatsapp):
    """Detect send message intent."""
    
    # Pattern: "send X to Y on whatsapp"
    m = re.match(
        r"^(?:send|message|text|tell|msg|ping)\s+"
        r"(?:(?:a\s+)?(?:message\s+)?)?"
        r"(?P<msg>.+?)\s+to\s+(?P<rec>.+?)"
        r"(?:\s+(?:on|via|through)\s+whatsapp)?\s*$",
        lower
    )
    if m:
        recipient = _clean_name(m.group("rec"))
        # Extract message from original text to preserve case
        msg_start = m.start("msg")
        msg_end = m.end("msg")
        message = _clean_message(text[msg_start:msg_end])
        # Remove trailing "on whatsapp" from recipient if present
        if recipient:
            recipient = re.sub(r"\s+(?:on|via|through)\s+whatsapp$", "", recipient, flags=re.I).strip()
        if recipient:
            return {
                "intent": INTENT_WHATSAPP_SEND,
                "application": "whatsapp",
                "recipient": recipient,
                "message": message,
                "confidence": HIGH_CONFIDENCE if has_whatsapp else MEDIUM_CONFIDENCE
            }
    
    # Pattern: "send whatsapp message to Y"
    m = re.match(
        r"^(?:send|message|text|tell|msg|ping)\s+"
        r"(?:a\s+)?(?:whatsapp\s+)?(?:message\s+)?"
        r"to\s+(?P<rec>.+?)"
        r"(?:\s+saying\s+(?P<msg>.+))?"
        r"(?:\s+(?:on|via|through)\s+whatsapp)?\s*$",
        lower
    )
    if m:
        recipient = _clean_name(m.group("rec"))
        message = _clean_message(m.group("msg") or "")
        # Remove trailing "on whatsapp" from recipient if present
        if recipient:
            recipient = re.sub(r"\s+(?:on|via|through)\s+whatsapp$", "", recipient, flags=re.I).strip()
        if recipient:
            return {
                "intent": INTENT_WHATSAPP_SEND,
                "application": "whatsapp",
                "recipient": recipient,
                "message": message,
                "confidence": HIGH_CONFIDENCE if has_whatsapp else MEDIUM_CONFIDENCE
            }
    
    # Pattern: "send X Y" (simple - recipient then message, no "to")
    m = re.match(
        r"^(?:send|message|text|msg|ping)\s+"
        r"(?P<rec>[A-Za-z][A-Za-z0-9 ]{0,30}?)\s+"
        r"(?P<msg>.+?)$",
        lower
    )
    if m:
        recipient = _clean_name(m.group("rec"))
        message = _clean_message(m.group("msg"))
        # Make sure recipient isn't actually a message word
        if recipient and recipient.lower() not in ("a", "the", "my", "on", "to", "that", "saying"):
            return {
                "intent": INTENT_WHATSAPP_SEND,
                "application": "whatsapp",
                "recipient": recipient,
                "message": message,
                "confidence": HIGH_CONFIDENCE if has_whatsapp else MEDIUM_CONFIDENCE
            }
    
    # Pattern: "message Y on whatsapp saying X"
    m = re.match(
        r"^(?:message|text|tell|msg)\s+(?P<rec>.+?)"
        r"(?:\s+(?:on|via|through)\s+whatsapp)?"
        r"\s+(?:saying|that|:)\s+(?P<msg>.+?)$",
        lower
    )
    if m:
        recipient = _clean_name(m.group("rec"))
        message = _clean_message(m.group("msg"))
        if recipient:
            return {
                "intent": INTENT_WHATSAPP_SEND,
                "application": "whatsapp",
                "recipient": recipient,
                "message": message,
                "confidence": HIGH_CONFIDENCE if has_whatsapp else MEDIUM_CONFIDENCE
            }
    
    # Pattern: "tell Y X" (with whatsapp context)
    m = re.match(
        r"^tell\s+(?P<rec>.+?)\s+(?P<msg>.+?)$",
        lower
    )
    if m and has_whatsapp:
        recipient = _clean_name(m.group("rec"))
        message = _clean_message(m.group("msg"))
        if recipient:
            return {
                "intent": INTENT_WHATSAPP_SEND,
                "application": "whatsapp",
                "recipient": recipient,
                "message": message,
                "confidence": HIGH_CONFIDENCE
            }
    
    # Pattern: "send/message/text on whatsapp" (no recipient - ask who)
    m = re.match(
        r"^(?:send|message|text|tell|msg|ping)\s+(?:on|via)\s+whatsapp\s*$",
        lower
    )
    if m:
        return {
            "intent": INTENT_WHATSAPP_SEND,
            "application": "whatsapp",
            "recipient": None,
            "message": None,
            "confidence": MEDIUM_CONFIDENCE
        }
    
    # Pattern: "X on whatsapp" (simple send - just open chat with X)
    # Exclude message verbs from being recipients
    msg_verbs = ("send", "message", "text", "tell", "msg", "ping", "forward", "write")
    m = re.match(
        r"^(?P<rec>\w+(?:\s+\w+)?)\s+(?:on|via)\s+whatsapp\s*$",
        lower
    )
    if m:
        recipient = _clean_name(m.group("rec"))
        if recipient and recipient.lower() not in msg_verbs:
            return {
                "intent": INTENT_WHATSAPP_OPEN,
                "application": "whatsapp",
                "recipient": recipient,
                "message": None,
                "confidence": HIGH_CONFIDENCE
            }
    
    return None


def _clean_name(name):
    """Clean a name extracted from text."""
    if not name:
        return None
    name = name.strip().strip(".,;:!?")
    # Remove articles
    name = re.sub(r"^(?:the|my|our|a|an)\s+", "", name, flags=re.I).strip()
    # Remove possessive
    name = re.sub(r"'s$", "", name, flags=re.I).strip()
    # Remove trailing prepositions
    name = re.sub(r"\s+(?:and|or|then|please)$", "", name, flags=re.I).strip()
    return name if name else None


def _clean_message(msg):
    """Clean a message extracted from text."""
    if not msg:
        return ""
    msg = msg.strip().strip(".,;:!?")
    # Remove wrapping quotes
    if len(msg) >= 2 and msg[0] in ("'", '"') and msg[-1] == msg[0]:
        msg = msg[1:-1]
    # Remove trailing prepositions
    msg = re.sub(r"\s+(?:on|via|through|please|thanks)$", "", msg, flags=re.I).strip()
    return msg


# ---------------------------------------------------------------------------
# Legacy parsing (for backward compatibility)
# ---------------------------------------------------------------------------

_MSG_VERBS = re.compile(
    r"^(?:send|message|text|tell|msg|ping|forward|write)\s+",
    re.IGNORECASE,
)

_TELL_RE = re.compile(
    r"^tell\s+(?P<recipient>[A-Za-z][A-Za-z0-9 ]{0,30}?)\s+"
    r"(?P<message>.+)?$",
    re.IGNORECASE,
)

_OPEN_CHAT_RE = re.compile(
    r"^open\s+(?P<recipient>[A-Za-z][A-Za-z0-9 ]{0,30})\s*"
    r"(?:'s?\s*)?(?:whatsapp\s+)?(?:chat|conversation|contact)$",
    re.IGNORECASE,
)


def _parse_command(text):
    """Parse recipient and message from text.
    Returns (recipient, message) or (None, None)."""
    # Try "tell X Y" pattern
    m = _TELL_RE.match(text)
    if m:
        r = _clean_name(m.group("recipient"))
        if r:
            return r, _clean_message(m.group("message"))
    
    # Try "open X's WhatsApp chat"
    m = _OPEN_CHAT_RE.match(text)
    if m:
        r = _clean_name(m.group("recipient"))
        if r:
            return r, ""
    
    # Try simple extraction
    return _extract_simple(text)


def _extract_simple(text):
    """Simple extraction: 'send Rahul hello' -> ('Rahul', 'hello')."""
    # Remove WhatsApp mentions
    cleaned = re.sub(r"\s*(?:on|via|in|through)\s+whatsapp\s*", " ", text, flags=re.I)
    cleaned = re.sub(r"\s*whatsapp\s*", " ", cleaned, flags=re.I)
    cleaned = cleaned.strip()
    
    # Try verb prefix patterns
    m = _MSG_VERBS.match(cleaned)
    if m:
        rest = cleaned[m.end():].strip()
        if not rest:
            return None, None
        # Handle "send X to Y" pattern
        to_match = re.match(r"^(.+?)\s+to\s+(.+?)$", rest, re.IGNORECASE)
        if to_match:
            msg_part = _clean_message(to_match.group(1))
            recipient = _clean_name(to_match.group(2))
            if recipient and msg_part:
                return recipient, msg_part
        # Handle "send X saying Y" pattern
        parts = re.split(r"\s*(?:,?\s*(?:that|saying|says|:))\s*", rest, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            return _clean_name(parts[0]), _clean_message(parts[1])
        # No separator - first word is recipient, rest is message
        words = rest.split()
        if len(words) >= 2:
            return _clean_name(words[0]), _clean_message(" ".join(words[1:]))
        elif len(words) == 1:
            return _clean_name(words[0]), ""
    
    return None, None


# ---------------------------------------------------------------------------
# WhatsApp UI automation
# ---------------------------------------------------------------------------

def _is_whatsapp_running():
    """Check if WhatsApp is running."""
    try:
        import psutil
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "").lower()
            if "whatsapp" in name:
                return True
    except Exception:
        pass
    return False


def _launch_whatsapp():
    """Launch WhatsApp. Returns True if launched or already running."""
    if _is_whatsapp_running():
        return True
    # Try desktop app first
    result = apps.launch_app("whatsapp")
    if result.get("ok"):
        time.sleep(3)
        return True
    # Try common desktop paths
    import os
    common_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\WhatsApp\WhatsApp.exe"),
    ]
    for path in common_paths:
        if os.path.isfile(path):
            try:
                os.startfile(path)
                time.sleep(3)
                return True
            except Exception:
                pass
    # Fallback to WhatsApp Web in browser
    try:
        import webbrowser
        webbrowser.open("https://web.whatsapp.com")
        time.sleep(4)
        return True
    except Exception:
        pass
    return False


def _focus_whatsapp():
    """Bring WhatsApp window to foreground."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        # Try WhatsApp desktop first
        hwnd = user32.FindWindowW(None, "WhatsApp")
        if hwnd:
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            return True
        # Try Chrome with WhatsApp Web
        hwnd = user32.FindWindowW(None, "Google Chrome")
        if hwnd:
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            return True
        # Try Edge with WhatsApp Web
        hwnd = user32.FindWindowW(None, "Microsoft Edge")
        if hwnd:
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            return True
    except Exception:
        pass
    return False


def _open_search():
    """Open WhatsApp search. Works for both desktop and web."""
    pccontrol.send_keys("ctrl+f")
    time.sleep(0.8)


def _type_and_search(name):
    """Type a name in WhatsApp search and wait for results."""
    pccontrol.send_keys("ctrl+a")
    time.sleep(0.1)
    pccontrol.type_text(name)
    time.sleep(1.5)


def _select_first_result():
    """Press Enter to select the first search result."""
    pccontrol.send_keys("enter")
    time.sleep(1)


def _type_message(message):
    """Type a message in the WhatsApp message box."""
    time.sleep(0.3)
    pccontrol.type_text(message)
    time.sleep(0.3)


def _send_message():
    """Press Enter to send the typed message."""
    pccontrol.send_keys("enter")
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# Skill handler
# ---------------------------------------------------------------------------

def handler(text, ctx):
    """WhatsApp messaging skill handler."""
    # First try structured intent detection
    intent = detect_intent(text)
    
    if intent is None:
        return None
    
    # Check for pending WhatsApp confirmation
    dec = confirm.check(text, {"whatsapp_send"})
    if dec is not None:
        if dec.get("cancelled"):
            return "Message cancelled."
        payload = dec.get("payload") or {}
        recipient = payload.get("recipient", "")
        message = payload.get("message", "")
        if message:
            _type_message(message)
            _send_message()
            return f"Message sent to {recipient}."
        return "No message to send."
    
    # Check for pending WhatsApp edit
    edit_re = re.compile(
        r"(?:edit|change|update)\s+(?:it\s+)?(?:to|message)\s*[:\-]?\s*['\"]?(.+?)['\"]?\s*$",
        re.IGNORECASE,
    )
    m = edit_re.search(text)
    if m:
        from ..utils import storage
        pending = storage.load("pending_confirm", None)
        if (pending and isinstance(pending, dict)
                and pending.get("action") == "whatsapp_send"):
            new_msg = m.group(1).strip().strip(".,;:!?")
            if new_msg:
                pending["payload"]["message"] = new_msg
                storage.save("pending_confirm", pending)
                rec = pending["payload"].get("recipient", "")
                return f"Updated message to: '{new_msg}' for {rec}. Send it?"
        return "No pending message to edit."
    
    # Handle based on intent
    intent_type = intent.get("intent")
    recipient = intent.get("recipient")
    message = intent.get("message")
    
    # Intent: Open WhatsApp
    if intent_type == INTENT_WHATSAPP_OPEN:
        if _launch_whatsapp():
            _focus_whatsapp()
            if recipient:
                # Open specific chat
                _open_search()
                _type_and_search(recipient)
                _select_first_result()
                return f"Opened WhatsApp chat with {recipient}."
            return "WhatsApp is open."
        return "WhatsApp is not installed or could not be launched."
    
    # Intent: Search chat
    if intent_type == INTENT_WHATSAPP_SEARCH:
        if not _launch_whatsapp():
            return "WhatsApp is not installed or could not be launched."
        _focus_whatsapp()
        _open_search()
        _type_and_search(recipient)
        _select_first_result()
        return f"Opened WhatsApp chat with {recipient}."
    
    # Intent: Send message
    if intent_type == INTENT_WHATSAPP_SEND:
        if not recipient:
            return "Who would you like to message on WhatsApp?"
        
        # Open WhatsApp
        if not _launch_whatsapp():
            return "WhatsApp is not installed or could not be launched."
        _focus_whatsapp()
        
        # Search for chat
        _open_search()
        _type_and_search(recipient)
        _select_first_result()
        
        # If no message given, just open the chat
        if not message:
            return f"Opened WhatsApp chat with {recipient}."
        
        # Show preview and request confirmation
        preview = (
            f"WhatsApp message to {recipient}:\n"
            f'"{message}"\n\n'
            f"Send it? (say 'yes' to send, 'no' to cancel, "
            f"or 'edit it to <new message>' to change)"
        )
        # Store for confirmation
        confirm.request(
            "whatsapp_send",
            f"Send to {recipient}: \"{message}\"",
            {"recipient": recipient, "message": message},
        )
        return preview
    
    return None
