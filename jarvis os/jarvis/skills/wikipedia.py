"""General knowledge and people lookup via the Wikipedia REST API.

Returns None (hands off to the LLM) when the page is missing, has no
extract, or the lookup fails - never a fabricated answer.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 20
UA = "JarvisOS/1.0 (personal assistant; contact: none)"

_TRIGGERS = ("who is", "who was", "who are", "what is", "what was", "what are",
             "tell me about", "define", "meaning of", "biography of")

# Queries about the user's own system should go to LLM, not Wikipedia
_EXCLUDE_PATTERNS = (
    r"\b(my|the|this|your)\s+(laptop|computer|pc|system|device|machine)\b",
    r"\b(status|specs|specifications|hardware|software)\b.*\b(of|for|about)\b.*\b(my|the|this|your)\b",
    r"\b(how much|how many|how fast|what kind)\b.*\b(ram|memory|cpu|disk|storage|battery)\b",
    # About JARVIS, not an article -- chat.py answers these first anyway.
    r"\byour\s+(name|age|purpose|identity|creator|maker|birthday)\b",
)

# Philosophical/complex questions should go to LLM, not Wikipedia
_EXCLUDE_TRIGGERS = (
    "meaning of life", "purpose of life", "why do we exist",
    "what is love", "what is happiness", "what is consciousness",
    "what is the meaning", "what is the purpose",
)

# Arithmetic is the maths skill's job. Left unguarded, a query like
# "5 times 6" was sent to Wikipedia's search, which always returns *something*
# -- and "what is 5 times 6" came back as an article about a rifle cartridge.
# Requires a digit on both sides of an operator, so "5 gum" or "who is 50 cent"
# still reach Wikipedia normally.
_ARITH_RE = re.compile(
    r"\d\s*(?:\+\s*\d|\-\s*\d|\*\s*\d|/\s*\d|x\s*\d|×\s*\d|"
    r"plus\s+\d|minus\s+\d|times\s+\d|divided\s+by\s+\d|and\s+\d)",
    re.IGNORECASE,
)


def _fetch_summary(title):
    url = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
           + urllib.parse.quote(title.replace(" ", "_")))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        if resp.status == 404:
            return None
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _search_title(query):
    url = ("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json"
           f"&srsearch={urllib.parse.quote(query)}&srlimit=1")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    hits = data.get("query", {}).get("search", [])
    return hits[0]["title"] if hits else None


def handler(text, ctx):
    lower = text.lower().strip()
    query = None
    for t in _TRIGGERS:
        if lower.startswith(t):
            query = lower[len(t):].strip().strip("?.!")
            break
    if not query:
        return None

    # Hand sums straight back: maths.py already declined them, and Wikipedia
    # would answer with whatever its fuzzy match happened to find.
    if _ARITH_RE.search(query):
        return None
    
    # Skip queries about user's own system (should go to LLM or system skills)
    for pattern in _EXCLUDE_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return None
    
    # Skip philosophical/complex questions (should go to LLM)
    for trigger in _EXCLUDE_TRIGGERS:
        if trigger in lower:
            return None
    
    try:
        title = _search_title(query)
        if not title:
            return None
        data = _fetch_summary(title)
        if not data or data.get("type") == "disambiguation":
            return None
        extract = (data.get("extract") or "").strip()
        if not extract:
            return None
        name = data.get("title", title)
        short = extract[:600] + ("..." if len(extract) > 600 else "")
        return f"{name}: {short}"
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError):
        return None
