"""Spoken-command wrappers shared by skills.

Voice input wraps the real command in politeness and attention words
("can you ...", "please ...", "hey ...", trailing commas from STT).
Every skill strips these identically before matching its own verbs.

Only a LEADING wrapper is ever removed, so message bodies and dictation
content are untouched. Skills with keystroke-injection surfaces
(pc type/press) must keep matching the original text and use this
only for their read-only branches.
"""

import re

WRAP_RE = re.compile(
    r"^(?:can you|could you|would you|will you|please|kindly|hey|okay|hi|hello|yo)[,\s]+(?:please\s+)?",
    re.IGNORECASE,
)


def strip_wrap(text):
    """Remove one leading polite/attention wrapper, if present."""
    return WRAP_RE.sub("", text or "").strip()
