"""Weather and temperature anywhere via Open-Meteo (free, no key)."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 20
UA = "JarvisOS/1.0 (personal assistant; contact: none)"

# What counts as asking about the weather. Kept deliberately narrow for "rain":
# bare "rain" as a trigger matched inside "train", "brainstorm" and "grain",
# so only a real rain question or a weather context after the word counts.
_WEATHER_RE = re.compile(
    r"\b(?:weather|forecast|temperature|humidity|degrees?|rainfall)\b"
    r"|\bhow\s+(?:hot|cold|warm|cool|much\s+rain)\b"
    r"|\b(?:will|would|is|are|was|were|does|do|did|has|have)\s+it\s+"
    r"(?:be\s+)?(?:going\s+to\s+)?(?:rain|raining)\b"
    r"|\b(?:rain|raining|rainy)\s+(?:in|at|today|now|tomorrow|tonight|this|next|outside)\b"
    r"|\bchance\s+of\s+rain\b"
    r"|\braining\b",
    re.I,
)

# Words that follow in|for|at|of but are never a city. Without this,
# "forecast for tomorrow" geocoded "tomorrow" and answered
# "I couldn't find 'tomorrow'", and "chance of rain today" looked up "rain".
_PLACE_STOP = {
    "today", "tomorrow", "tonight", "now", "later", "soon", "this", "week",
    "weekend", "day", "days", "hour", "hours", "morning", "afternoon",
    "evening", "night", "next", "current", "currently",
    "the", "a", "an", "in", "for", "at", "of", "here", "there", "outside",
    "inside", "around", "me", "my", "us", "some", "any",
    "rain", "raining", "rainy", "weather", "forecast", "temperature",
    "humidity", "degrees", "degree",
}


def _clean_place(raw):
    """Strip time/filler words from a captured place name."""
    words = re.split(r"\s+", (raw or "").strip().strip("?.!"))
    while words and words[0].lower() in _PLACE_STOP:
        words.pop(0)
    while words and words[-1].lower() in _PLACE_STOP:
        words.pop()
    return " ".join(words) or None

_WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "freezing drizzle", 61: "light rain", 63: "rain",
    65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow",
    73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light showers",
    81: "showers", 82: "violent showers", 85: "light snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


def _geocode(place):
    url = ("https://geocoding-api.open-meteo.com/v1/search?name="
           + urllib.parse.quote(place) + "&count=1&language=en&format=json")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    hits = data.get("results") or []
    if not hits:
        return None
    h = hits[0]
    return h["latitude"], h["longitude"], h.get("name", place)


def _forecast(lat, lon):
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
           "weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min&timezone=auto")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def handler(text, ctx):
    lower = text.lower().strip()
    # Word-bounded and weather-shaped. Plain substring let "brainstorm",
    # "take the train" and "grain" ask for a city, and any sentence merely
    # mentioning rain ("write me a poem about rain") was hijacked by us.
    if not _WEATHER_RE.search(lower):
        return None
    m = re.search(r"\b(?:in|for|at|of)\b\s+([a-zA-Z][a-zA-Z\s\-']+)", lower)
    place = _clean_place(m.group(1)) if m else None
    if not place and ctx and ctx.get("location"):
        place = ctx["location"]
    if not place:
        return "Which city? Set a default with: location <city>."
    try:
        geo = _geocode(place)
        if not geo:
            return f"I couldn't find '{place}'."
        lat, lon, name = geo
        fc = _forecast(lat, lon)
        cur = fc.get("current", {})
        daily = fc.get("daily", {})
        temp = cur.get("temperature_2m")
        cond = _WMO.get(cur.get("weather_code"), "changing skies")
        feels = cur.get("apparent_temperature")
        hum = cur.get("relative_humidity_2m")
        himax = (daily.get("temperature_2m_max") or [None])[0]
        lomin = (daily.get("temperature_2m_min") or [None])[0]
        parts = [f"{name}: {temp}\u00b0C, {cond}"]
        if feels is not None:
            parts.append(f"feels like {feels}\u00b0C")
        if himax is not None and lomin is not None:
            parts.append(f"high {himax}\u00b0C / low {lomin}\u00b0C")
        if hum is not None:
            parts.append(f"humidity {hum}%")
        return ". ".join(parts) + "."
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError):
        return "Weather service is unreachable at the moment."
