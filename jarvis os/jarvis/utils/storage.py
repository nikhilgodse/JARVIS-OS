import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
DATA_DIR = os.path.normpath(DATA_DIR)


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def save(name: str, data):
    _ensure_dir()
    path = os.path.join(DATA_DIR, f"{name}.json")
    tmp = path + f".tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def load(name: str, fallback=None):
    _ensure_dir()
    path = os.path.join(DATA_DIR, f"{name}.json")
    if not os.path.exists(path):
        return fallback if fallback is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return fallback if fallback is not None else {}
