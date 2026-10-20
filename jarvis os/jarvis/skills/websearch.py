"""Web search skill using DuckDuckGo's free Instant Answer API (no key)."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 20
UA = "JarvisOS/1.0 (personal assistant; contact: none)"

_WORDS = ("search the web", "web search", "search for", "search web",
          "look up", "find out", "google", "search internet", "what does the internet say")


def handler(text, ctx):
    lower = text.lower()
    query = None
    for w in ("search the web for", "web search for", "search for", "search web for",
              "look up", "find out about", "google"):
        if w in lower:
            query = lower.split(w, 1)[1].strip().strip("?")
            break
    if not query and any(lower.startswith(w) for w in ("search", "google", "searchtheweb")):
        pass
    if not query:
        for t in _WORDS:
            if lower.startswith(t):
                query = lower[len(t):].strip().strip("?")
                break
    if not query:
        return None

    try:
        url = "https://api.duckduckgo.com/?q=" + urllib.parse.quote(query) + "&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            return abstract[:600] + ("..." if len(abstract) > 600 else "")

        results = [t for t in data.get("RelatedTopics", []) if isinstance(t, dict) and t.get("Text")]
        if results:
            return "Top result: " + results[0]["Text"][:600]

        return wikipedia_fallback(query)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        return "Web search service is unreachable at the moment."


def wikipedia_fallback(query):
    """Get a short answer for the query from Wikipedia search."""
    try:
        url = ("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json"
               f"&srsearch={urllib.parse.quote(query)}&srlimit=1")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        hits = data.get("query", {}).get("search", [])
        if not hits:
            return f"I could not find solid results for '{query}'."
        title = hits[0]["title"]
        sum_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_"))
        req = urllib.request.Request(sum_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        extract = (data.get("extract") or "").strip()
        if extract:
            return f"{data.get('title', title)}: {extract[:600]}" + ("..." if len(extract) > 600 else "")
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        pass
    return f"I could not find solid results for '{query}'."
