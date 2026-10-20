"""Master-password gate. Salted hash lives in data/config.json (flat schema)."""

import datetime
import getpass
import hashlib
import os

from ..utils import storage

DEFAULT_PASSWORD = "jarvis"

_authenticated = False


def _cfg():
    cfg = storage.load("config", {})
    return cfg if isinstance(cfg, dict) else {}


def _save_cfg(cfg):
    storage.save("config", cfg)


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"),
                               salt.encode("utf-8"), 200_000).hex()


def is_configured():
    return bool(_cfg().get("master_hash"))


def register(password=DEFAULT_PASSWORD):
    salt = os.urandom(16).hex()
    cfg = _cfg()
    cfg["salt"] = salt
    cfg["master_hash"] = _hash(password, salt)
    cfg["authenticated"] = False
    _save_cfg(cfg)


def authenticate(password):
    global _authenticated
    cfg = _cfg()
    salt, want = cfg.get("salt"), cfg.get("master_hash")
    _authenticated = bool(salt and want and _hash(password, salt) == want)
    cfg["authenticated"] = _authenticated
    if _authenticated:
        cfg["last_login"] = datetime.datetime.now().isoformat()
    _save_cfg(cfg)
    return _authenticated


def is_authenticated():
    return _authenticated


def logout():
    global _authenticated
    _authenticated = False
    cfg = _cfg()
    cfg["authenticated"] = False
    _save_cfg(cfg)


def prompt_hidden(prompt="Password: "):
    try:
        return getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""
