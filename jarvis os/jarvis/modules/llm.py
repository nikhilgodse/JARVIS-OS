"""OpenAI-compatible LLM client with provider abstraction (stdlib only).

Architecture:
    AI Provider Router
        ├── OllamaProvider (local, default)
        └── NvidiaNimProvider (cloud)

Precedence for provider selection:
    AI_PROVIDER env var -> auto-detect from config -> default to ollama

Precedence for credentials:
    JARVIS_LLM_* env vars > .env file > data/config.json > built-in defaults

Supported providers:
    - Ollama (local, no API key needed)
    - NVIDIA NIM (cloud, requires API key)

The existing complete() API is preserved so chat.py and other callers
do not need to change.
"""

import json
import os
import urllib.error
import urllib.request

from ..utils import storage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OLLAMA_ENDPOINT = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "qwen2.5:7b-instruct-q3_K_M"
NVIDIA_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "nvidia/llama-3.1-nemotron-70b-instruct"
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"
TIMEOUT = 90
MAX_RETRIES = 2

# Guardrail: the model answers and reasons, but computer actions run through
# verified local tools. It must never invent success for actions it did not
# perform and cannot verify.
GUARDRAIL = (
    "You are JARVIS, a computer assistant. Answer conversationally and "
    "reason about the user's request, but never claim to have opened an "
    "application, searched the web, changed a setting, or performed any "
    "computer action - those run through separate verified tools, and only "
    "their confirmed results count as done. If asked to do something on "
    "the computer, say what you would do and ask which tool result to use. "
    "Never fabricate search results, prices, specifications, or file "
    "contents. When unsure, say so briefly.\n\n"
    "Composing text is always in scope: when the user asks for an email, "
    "code, a poem, a summary, an outline or an explanation, write it in "
    "full and lead with it. Only running, sending or saving it would be a "
    "computer action, which is what the first paragraph rules out - the "
    "writing itself never is.\n\n"
    "Style: dry, unhurried, competent. Answer in one or two short sentences "
    "and then stop - no preamble, no recap, no bullet lists, no restating "
    "the question, and no offers of further help. Lead with the answer "
    "itself. Drop filler such as 'Certainly', 'Of course', 'Great question' "
    "and 'I hope this helps'. Never add 'sir' or 'boss' to every line; use "
    "it rarely, if at all. If the request is trivial, a few words is the "
    "right length. Match your length to what was actually asked."
)


# ---------------------------------------------------------------------------
# .env loader (stdlib only, no python-dotenv)
# ---------------------------------------------------------------------------

def _load_dotenv():
    """Load .env file if it exists. Does not overwrite existing env vars."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if key and value and key not in os.environ:
                        os.environ[key] = value
    except Exception:
        pass


_load_dotenv()


# ---------------------------------------------------------------------------
# Provider base class
# ---------------------------------------------------------------------------

def _connect_url(url: str) -> str:
    """Endpoint to actually open the socket to.

    Ollama binds IPv4 only, but on Windows `localhost` resolves to ::1 first
    (getaddrinfo yields AF_INET6 before AF_INET), so every request burned ~2s
    on a doomed IPv6 connect before falling back -- a 2.6s /api/status poll,
    and ~2s added to each LLM call. The stored endpoint is deliberately left
    alone so settings() still reports exactly what the user configured.
    """
    return (url or "").replace("://localhost", "://127.0.0.1")


class LLMProvider:
    """Base class for LLM providers."""

    name = "base"

    def __init__(self, api_key="", endpoint="", model="", timeout=TIMEOUT):
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout

    def is_configured(self):
        """Return True if this provider has enough config to attempt a request."""
        return bool(self.endpoint)

    def complete(self, messages, timeout=None):
        """Send chat completion. Returns assistant text or raises RuntimeError."""
        raise NotImplementedError

    def health_check(self):
        """Return dict with health status. Subclasses override."""
        return {"provider": self.name, "status": "unknown"}

    def _send_request(self, body_dict, timeout=None):
        """Shared HTTP POST logic for OpenAI-compatible endpoints."""
        timeout = timeout or self.timeout
        body = json.dumps(body_dict).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "JarvisOS/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(_connect_url(self.endpoint), data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            code = e.code
            try:
                detail = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                detail = str(e)
            if code == 401 or code == 403:
                raise RuntimeError(f"Authentication failed ({code}): check API key")
            if code == 404:
                raise RuntimeError(f"Model/endpoint not found (404): {detail}")
            if code == 429:
                raise RuntimeError(f"Rate limited (429): try again later")
            if code >= 500:
                raise RuntimeError(f"Server error ({code}): {detail}")
            raise RuntimeError(f"HTTP {code}: {detail}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Connection failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Request failed: {e}")

    def _parse_response(self, data):
        """Extract assistant text from OpenAI-compatible response."""
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            raise RuntimeError("LLM returned an unexpected response shape.")


# ---------------------------------------------------------------------------
# Ollama Provider
# ---------------------------------------------------------------------------

class OllamaProvider(LLMProvider):
    """Local Ollama LLM provider."""

    name = "ollama"

    def __init__(self, api_key="", endpoint=None, model=None, timeout=TIMEOUT):
        super().__init__(
            api_key=api_key or "ollama-local",
            endpoint=endpoint or OLLAMA_ENDPOINT,
            model=model or OLLAMA_MODEL,
            timeout=timeout,
        )

    def is_configured(self):
        return bool(self.endpoint)

    def complete(self, messages, timeout=None):
        msgs = list(messages or [])
        if not msgs or msgs[0].get("role") != "system":
            msgs = [{"role": "system", "content": GUARDRAIL}] + msgs
        body = {
            "model": self.model,
            "messages": msgs,
            "temperature": 0.7,
        }
        data = self._send_request(body, timeout)
        return self._parse_response(data)

    def health_check(self):
        result = {"provider": self.name, "endpoint": self.endpoint,
                  "model": self.model, "server_reachable": False,
                  "model_available": False, "status": "offline"}
        # Check if server is reachable
        try:
            req = urllib.request.Request(
                _connect_url(self.endpoint).replace("/v1/chat/completions", "/api/tags"),
                headers={"User-Agent": "JarvisOS/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                result["server_reachable"] = True
                models = [m.get("name", "") for m in data.get("models", [])]
                result["model_available"] = any(
                    self.model in m for m in models)
                result["status"] = "online" if result["model_available"] else "degraded"
        except Exception:
            result["status"] = "offline"
        return result


# ---------------------------------------------------------------------------
# NVIDIA NIM Provider
# ---------------------------------------------------------------------------

class NvidiaNimProvider(LLMProvider):
    """NVIDIA NIM cloud LLM provider."""

    name = "nvidia"

    def __init__(self, api_key="", endpoint=None, model=None, timeout=TIMEOUT):
        super().__init__(
            api_key=api_key,
            endpoint=endpoint or NVIDIA_ENDPOINT,
            model=model or NVIDIA_MODEL,
            timeout=timeout,
        )

    def is_configured(self):
        return bool(self.api_key and self.endpoint)

    def complete(self, messages, timeout=None):
        if not self.api_key:
            raise RuntimeError("NVIDIA NIM requires an API key. Set NVIDIA_API_KEY in .env")
        msgs = list(messages or [])
        if not msgs or msgs[0].get("role") != "system":
            msgs = [{"role": "system", "content": GUARDRAIL}] + msgs
        body = {
            "model": self.model,
            "messages": msgs,
            "temperature": 0.7,
        }
        data = self._send_request(body, timeout)
        return self._parse_response(data)

    def health_check(self):
        result = {"provider": self.name, "endpoint": self.endpoint,
                  "model": self.model, "api_key_configured": bool(self.api_key),
                  "endpoint_reachable": False, "model_available": False,
                  "status": "offline"}
        if not self.api_key:
            result["status"] = "no_api_key"
            return result
        # Check endpoint reachability
        try:
            req = urllib.request.Request(
                self.endpoint.replace("/chat/completions", "/models"),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "User-Agent": "JarvisOS/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                result["endpoint_reachable"] = True
                models = [m.get("id", "") for m in data.get("data", [])]
                result["model_available"] = self.model in models
                result["status"] = "online" if result["model_available"] else "model_not_deployed"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                result["status"] = "auth_error"
            elif e.code == 404:
                result["status"] = "endpoint_not_found"
            else:
                result["status"] = "error"
        except Exception:
            result["status"] = "offline"
        return result


# ---------------------------------------------------------------------------
# Provider Router (selection + fallback)
# ---------------------------------------------------------------------------

class ProviderRouter:
    """Routes requests to the configured provider with optional fallback."""

    def __init__(self):
        self._providers = {}
        self._primary_name = ""
        self._fallback_name = ""
        self._auto_fallback = False

    def configure(self):
        """Configure providers from environment and config."""
        cfg = storage.load("config", {})
        if not isinstance(cfg, dict):
            cfg = {}

        # Determine provider selection mode
        ai_provider = os.environ.get("AI_PROVIDER", "").lower()
        primary = os.environ.get("AI_PRIMARY_PROVIDER", "").lower()
        fallback = os.environ.get("AI_FALLBACK_PROVIDER", "").lower()
        auto_fallback = os.environ.get("AI_AUTO_FAILOVER", "").lower() in ("true", "1", "yes")

        # Build Ollama provider
        ollama_key = (os.environ.get("JARVIS_LLM_API_KEY", "")
                      or cfg.get("llm_api_key", ""))
        ollama_endpoint = (os.environ.get("OLLAMA_ENDPOINT", "")
                           or os.environ.get("JARVIS_LLM_ENDPOINT", "")
                           or cfg.get("llm_endpoint", "")
                           or OLLAMA_ENDPOINT)
        ollama_model = (os.environ.get("OLLAMA_MODEL", "")
                        or os.environ.get("JARVIS_LLM_MODEL", "")
                        or cfg.get("llm_model", "")
                        or OLLAMA_MODEL)
        self._providers["ollama"] = OllamaProvider(
            api_key=ollama_key, endpoint=ollama_endpoint, model=ollama_model)

        # Build NVIDIA provider
        nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
        nvidia_endpoint = os.environ.get("NVIDIA_BASE_URL", "") or NVIDIA_ENDPOINT
        nvidia_model = os.environ.get("NVIDIA_MODEL", "") or NVIDIA_MODEL
        self._providers["nvidia"] = NvidiaNimProvider(
            api_key=nvidia_key, endpoint=nvidia_endpoint, model=nvidia_model)

        # Determine primary provider
        if ai_provider in ("ollama", "nvidia"):
            self._primary_name = ai_provider
        elif primary in ("ollama", "nvidia"):
            self._primary_name = primary
        elif nvidia_key:
            # Auto-detect: if NVIDIA key is set, prefer NVIDIA
            self._primary_name = "nvidia"
        else:
            self._primary_name = "ollama"

        # Determine fallback provider
        if fallback in ("ollama", "nvidia") and fallback != self._primary_name:
            self._fallback_name = fallback
        elif auto_fallback:
            self._fallback_name = "ollama" if self._primary_name == "nvidia" else "nvidia"
        else:
            self._fallback_name = ""

        self._auto_fallback = auto_fallback

    @property
    def primary(self):
        return self._providers.get(self._primary_name)

    @property
    def fallback(self):
        return self._providers.get(self._fallback_name) if self._fallback_name else None

    @property
    def primary_name(self):
        return self._primary_name

    @property
    def fallback_name(self):
        return self._fallback_name

    @property
    def auto_fallback(self):
        return self._auto_fallback

    def complete(self, messages, timeout=None):
        """Send to primary, fall back to secondary if primary fails."""
        last_error = None

        # Try primary provider
        provider = self.primary
        if provider and provider.is_configured():
            try:
                return provider.complete(messages, timeout)
            except RuntimeError as e:
                last_error = e
                # Only fall back for transient errors, not auth errors
                err_str = str(e).lower()
                if "authentication" in err_str or "auth" in err_str:
                    raise
                if not self._auto_fallback or not self.fallback:
                    raise

        # Try fallback provider
        if self._auto_fallback and self.fallback and self.fallback.is_configured():
            try:
                return self.fallback.complete(messages, timeout)
            except RuntimeError as e:
                # Both failed - raise the primary error
                if last_error:
                    raise last_error
                raise

        # No configured provider
        if last_error:
            raise last_error
        raise RuntimeError("No LLM provider configured. Set AI_PROVIDER in .env or config.")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_router = None


def _get_router():
    global _router
    if _router is None:
        _router = ProviderRouter()
        _router.configure()
    return _router


def reset_router():
    """Force reconfiguration on next call (for testing or runtime changes)."""
    global _router
    _router = None


# ---------------------------------------------------------------------------
# Public API (backward compatible)
# ---------------------------------------------------------------------------

def settings() -> dict:
    """Return current provider settings. Backward compatible with existing callers."""
    router = _get_router()
    provider = router.primary
    if provider:
        return {
            "api_key": provider.api_key,
            "endpoint": provider.endpoint,
            "model": provider.model,
        }
    return {"api_key": "", "endpoint": OLLAMA_ENDPOINT, "model": OLLAMA_MODEL}


def is_configured() -> bool:
    """Return True if any provider is configured."""
    router = _get_router()
    return bool((router.primary and router.primary.is_configured()) or
                (router.fallback and router.fallback.is_configured()))


def set_config(api_key: str = None, endpoint: str = None, model: str = None):
    """Update LLM config in data/config.json. Backward compatible."""
    cfg = storage.load("config", {})
    if not isinstance(cfg, dict):
        cfg = {}
    if api_key is not None:
        cfg["llm_api_key"] = api_key
    if endpoint is not None:
        cfg["llm_endpoint"] = endpoint
    if model is not None:
        cfg["llm_model"] = model
    storage.save("config", cfg)
    reset_router()


def complete(messages: list, timeout: int = TIMEOUT):
    """Chat completion. Returns the assistant text or raises RuntimeError."""
    router = _get_router()
    return router.complete(messages, timeout)


def doctor() -> str:
    """Diagnostic output for all providers. Never reveals API keys."""
    router = _get_router()
    lines = ["  AI PROVIDERS", ""]

    # Check each provider
    for name in ("ollama", "nvidia"):
        provider = router._providers.get(name)
        if not provider:
            continue
        health = provider.health_check()
        is_primary = (name == router.primary_name)
        is_fallback = (name == router.fallback_name)
        tag = " (primary)" if is_primary else (" (fallback)" if is_fallback else "")

        lines.append(f"  {provider.name.upper()}{tag}:")
        if name == "nvidia":
            key_set = bool(provider.api_key)
            lines.append(f"    API Key: {'CONFIGURED' if key_set else 'NOT SET'}")
            lines.append(f"    Endpoint: {'REACHABLE' if health.get('endpoint_reachable') else 'UNREACHABLE'}")
            lines.append(f"    Model: {'AVAILABLE' if health.get('model_available') else 'UNAVAILABLE'}")
        else:
            lines.append(f"    Server: {'ONLINE' if health.get('server_reachable') else 'OFFLINE'}")
            lines.append(f"    Model: {'AVAILABLE' if health.get('model_available') else 'UNAVAILABLE'}")
        lines.append(f"    Status: {health.get('status', 'unknown').upper()}")
        lines.append("")

    # Current active provider
    lines.append(f"  Active: {router.primary_name.upper()}")
    if router.auto_fallback:
        lines.append(f"  Fallback: {router.fallback_name.upper() if router.fallback_name else 'NONE'}")
        lines.append(f"  Auto-failover: ENABLED")
    else:
        lines.append(f"  Auto-failover: DISABLED")

    return "\n".join(lines)


def provider_info() -> dict:
    """Return structured provider info for API responses."""
    router = _get_router()
    health_primary = router.primary.health_check() if router.primary else {}
    health_fallback = router.fallback.health_check() if router.fallback else None
    return {
        "primary": router.primary_name,
        "fallback": router.fallback_name or None,
        "auto_fallback": router.auto_fallback,
        "primary_health": health_primary,
        "fallback_health": health_fallback,
    }
