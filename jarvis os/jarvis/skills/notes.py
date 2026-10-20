"""Remember and recall notes ("remember X", "what do you remember")."""

import re

from ..utils import storage
from .phrases import strip_wrap


def _notes():
    data = storage.load("notes", {})
    return data if isinstance(data, dict) else {}


def handler(text, ctx):
    # Voice wrappers first ("please remember X"); note bodies follow the
    # verb so they are never affected by the strip.
    lower = strip_wrap(text).lower().strip()

    m = re.match(r"^remember\s+(?:that\s+)?(.+)$", lower)
    if m:
        body = m.group(1).strip().strip("?.!")
        if " is " in body:
            key, _, value = body.partition(" is ")
        elif "=" in body:
            key, _, value = body.partition("=")
        else:
            key, value = body, "noted"
        key, value = key.strip(), value.strip()
        if not key or not value:
            return None
        notes = _notes()
        notes[key] = value
        storage.save("notes", notes)
        return f"Remembered: {key}."

    m2 = re.match(r"^(?:recall|what is my|whats my)\s+(.+)$", lower)
    if m2:
        key = m2.group(1).strip().strip("?.!")
        notes = _notes()
        for k, v in notes.items():
            if key in k or k in key:
                return f"{k}: {v}"
        return f"I don't remember anything about '{key}'."

    if re.match(r"^(what do you remember|recall|show (my )?notes|list notes|my notes)\b", lower):
        notes = _notes()
        if not notes:
            return "I don't have any notes yet."
        return "Notes: " + "; ".join(f"{k} = {v}" for k, v in list(notes.items())[:10])

    m = re.match(r"^forget\s+(?:that\s+)?(.+)$", lower)
    if m:
        key = m.group(1).strip().strip("?.!")
        notes = _notes()
        hit = next((k for k in notes if key in k or k in key), None)
        if hit:
            del notes[hit]
            storage.save("notes", notes)
            return f"Forgot: {hit}."
        return f"I don't have a note about '{key}'."

    return None
