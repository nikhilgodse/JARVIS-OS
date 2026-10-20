"""File and folder control through natural language.

- "open downloads / documents / desktop / pictures / videos / music [folder]"
- "show me files created today"
- "find my python files" / "find pdf files" / "find file named X"
- "create a folder called X" / "create file X"
- "delete / remove file X" (two-step: say 'yes' to confirm)

Delete safety: names must match EXACT case (Windows treats 'Jarvis' and
'jarvis' as the same file), must stay inside the working folder, and the
confirm prompt always shows the resolved path.
"""

import datetime
import os
import re
import shutil

from ..modules.files import FileManager, exact_entry
from . import confirm

_FOLDERS = {
    "downloads": "Downloads", "documents": "Documents", "desktop": "Desktop",
    "pictures": "Pictures", "videos": "Videos", "music": "Music",
}

_KINDS = {
    "python": (".py",), "pdf": (".pdf",), "word": (".docx", ".doc"),
    "excel": (".xlsx", ".xls"), "text": (".txt",), "note": (".txt", ".md"),
    "image": (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"),
    "picture": (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"),
    "photo": (".png", ".jpg", ".jpeg"),
    "song": (".mp3", ".wav", ".flac"), "music": (".mp3", ".wav", ".flac"),
    "video": (".mp4", ".mkv", ".avi", ".mov"), "movie": (".mp4", ".mkv", ".avi"),
    "zip": (".zip", ".rar", ".7z"), "archive": (".zip", ".rar", ".7z"),
    "powerpoint": (".pptx", ".ppt"), "presentation": (".pptx", ".ppt"),
}

_OPEN_FOLDER_RE = re.compile(
    r"^(?:open|show|go to)\s+(?:my\s+|the\s+)?"
    r"(downloads|documents|desktop|pictures|videos|music)(?:\s+folder)?$", re.I)
_TODAY_RE = re.compile(r"files?\s+(?:created|modified|made|added)\s+today", re.I)
_FIND_KIND_RE = re.compile(r"^find\s+(?:my\s+|the\s+|all\s+)?(.+?)\s+files?$", re.I)
_FIND_NAMED_RE = re.compile(
    r"^(?:find|locate|where is|where are)\s+(?:the\s+|my\s+)?"
    r"(?:file|folder|directory)\s+(?:named\s+|called\s+)?(.+)$", re.I)
_MAKE_DIR_RE = re.compile(
    r"^(?:create|make|new)\s+(?:a\s+|me\s+|me a\s+)?(?:new\s+)?"
    r"(?:folder|directory)\s+(?:called\s+|named\s+)?(.+)$", re.I)
_MAKE_FILE_RE = re.compile(
    r"^(?:create|make|new)\s+(?:a\s+|me\s+|me a\s+)?(?:new\s+)?"
    r"file\s+(?:called\s+|named\s+)?(.+)$", re.I)
_DELETE_RE = re.compile(
    r"^(?:delete|remove)\s+(?:the\s+|my\s+)?(?:file\s+|folder\s+|directory\s+)?(.+)$",
    re.I)

# "open jarvis os file in desktop" -> name "jarvis os": strip location tails
# and standalone file/folder words.
_LOCATION_TAIL_RE = re.compile(
    r"\s+(in|on|from)\s+(?:the\s+|my\s+)?"
    r"(desktop|documents|downloads|pictures|videos|music|laptop|computer|this pc|files)\s*$",
    re.I)


def _shell_path(csidl):
    """Windows known-folder path (real Desktop/Documents, not guesses)."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        rc = ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
        if rc == 0 and buf.value:
            return buf.value
    except Exception:
        pass
    return None


def _search_roots(cwd):
    roots = []
    home = os.path.expanduser("~")
    desk = _shell_path(0x10) or os.path.join(home, "Desktop")
    docs = _shell_path(0x05) or os.path.join(home, "Documents")
    for r in (cwd, desk, docs, home):
        if r and os.path.isdir(r) and r not in roots:
            roots.append(r)
    return roots


def _clean_local_query(text):
    t = re.sub(r"^(?:open|show|go to|launch|browse)\s+", "", (text or "").strip(),
               flags=re.IGNORECASE).strip()
    t = _LOCATION_TAIL_RE.sub("", t).strip()
    t = re.sub(r"^(?:the|my|a|an)\s+", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\s*\bfiles?\b\s*", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\bfolders?\b\s*", " ", t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()


def _open_path(path, label):
    try:
        os.startfile(path)
        return f"Opening {label}."
    except OSError as e:
        return f"I couldn't open {label}: {e}"


def open_local_target(text, cwd):
    """Open a local file/folder by name before any web fallback.

    Returns a reply string when the laptop has it (opened, ambiguous, or
    failed honestly), else None so web resolution can proceed."""
    q = _clean_local_query(text)
    if not q or len(q) < 2:
        return None
    cwd = cwd or os.getcwd()
    # literal path that exists (absolute or relative to cwd)
    for cand in (q, os.path.join(cwd, q)):
        if os.path.exists(cand):
            return _open_path(cand, os.path.basename(cand) or cand)
    roots = _search_roots(cwd)
    # exact, then case-insensitive exact
    for ci in (False, True):
        for root in roots:
            try:
                entries = os.listdir(root)
            except OSError:
                continue
            for e in entries:
                if (e == q) if not ci else (e.lower() == q.lower()):
                    return _open_path(os.path.join(root, e), e)
    # single unambiguous substring match (top level + cwd tree)
    cands = []
    for root in roots:
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for e in entries:
            if q.lower() in e.lower():
                cands.append(os.path.join(root, e))
    for p in _walk(cwd):
        if q.lower() in os.path.basename(p).lower() and p not in cands:
            cands.append(p)
    seen, uniq = set(), []
    for c in cands:
        cl = c.lower()
        if cl not in seen:
            seen.add(cl)
            uniq.append(c)
    if len(uniq) == 1:
        return _open_path(uniq[0], os.path.basename(uniq[0]))
    if len(uniq) > 1:
        shown = ", ".join(os.path.basename(u) for u in uniq[:5])
        more = f" (and {len(uniq) - 5} more)" if len(uniq) > 5 else ""
        return f"I found several matches: {shown}{more}. Which one?"
    return None


def _fm(ctx):
    fm = FileManager()
    if ctx and ctx.get("cwd"):
        fm.cwd = ctx["cwd"]
    return fm


def open_folder_arg(arg):
    """Router helper: 'open downloads' -> reply string or None."""
    text = (arg or "").strip()
    m = _OPEN_FOLDER_RE.match(text) or _OPEN_FOLDER_RE.match("open " + text)
    if not m:
        return None
    name = m.group(1).lower()
    path = os.path.join(os.path.expanduser("~"), _FOLDERS[name])
    if not os.path.isdir(path):
        return f"I couldn't find your {name} folder."
    try:
        os.startfile(path)
        return f"Opening your {name} folder."
    except OSError as e:
        return f"I couldn't open the {name} folder: {e}"


def find_files_reply(query, cwd):
    """Router helper: '<kind> files' search -> reply string or None."""
    q = re.sub(r"^for\s+", "", (query or "").strip(), flags=re.IGNORECASE)
    m = _FIND_KIND_RE.match(q) or _FIND_KIND_RE.match("find " + q)
    if not m:
        return None
    kind = m.group(1).strip().strip("?.!")
    if not kind or kind in ("my", "the", "all"):
        return None
    fm = FileManager()
    fm.cwd = cwd
    return _find_kind(kind, fm)


def resolve_delete(name, cwd):
    """Resolve a delete target exactly. Returns (resolved_path, error).

    resolved_path set + error None means safe to ask-to-delete. Anything
    else is a refusal with the reason (no match, case-variant, escape)."""
    base = os.path.basename((name or "").rstrip("/\\")).strip()
    if not base or base in (".", ".."):
        return None, f"Refusing to delete '{name}'."
    root = os.path.abspath(cwd)
    parent = os.path.abspath(os.path.join(root, os.path.dirname(name or "")))
    if parent != root and not parent.startswith(root + os.sep):
        return None, "I won't delete outside the working folder."
    if parent == root and os.path.abspath(os.path.join(root, base)) == root:
        return None, f"Refusing to delete '{name}'."
    exact = exact_entry(parent, base)
    if exact is None:
        return None, f"Not found: '{name}'."
    if exact != base:
        return None, (f"No exact match for '{name}'. Did you mean '{exact}'? "
                       "Use the exact name - Windows treats them as the same file.")
    return os.path.join(parent, exact), None


def handler(text, ctx):
    lower = (text or "").lower().strip()
    if not lower or "timer" in lower or "alarm" in lower:
        return None

    # pending delete confirmation (this skill's action only)
    dec = confirm.check(text, {"delete"})
    if dec is not None:
        if dec.get("cancelled"):
            return "Cancelled."
        return _do_delete((dec.get("payload") or {}).get("path"))

    # open well-known folders
    reply = open_folder_arg(lower)
    if reply:
        return reply

    # files created/modified today
    if _TODAY_RE.search(lower):
        return _find_today(_fm(ctx))

    # find "<kind> files"
    m = _FIND_KIND_RE.match(lower)
    if m:
        kind = m.group(1).strip().strip("?.!")
        if kind and kind not in ("my", "the", "all"):
            return _find_kind(kind, _fm(ctx))
        return None

    # find file/folder named X
    m = _FIND_NAMED_RE.match(lower)
    if m:
        return _find_named(m.group(1).strip().strip("?.!"), _fm(ctx))

    # create folder / file
    m = _MAKE_DIR_RE.match(lower)
    if m:
        name = m.group(1).strip().strip("?.!\"'")
        if not name or name in ("a folder", "folder"):
            return None
        fm = _fm(ctx)
        hit = exact_entry(fm.cwd, os.path.basename(name.rstrip("/\\")))
        if hit is not None and hit != os.path.basename(name.rstrip("/\\")):
            return (f"'{name}' collides with existing '{hit}' "
                    "(Windows names are case-insensitive).")
        target = os.path.join(fm.cwd, name)
        try:
            os.makedirs(target, exist_ok=True)
            return f"Done. The folder '{name}' has been created."
        except OSError as e:
            return f"I couldn't create '{name}': {e}"
    m = _MAKE_FILE_RE.match(lower)
    if m:
        name = m.group(1).strip().strip("?.!\"'")
        if not name or name in ("a file", "file"):
            return None
        fm = _fm(ctx)
        target = os.path.join(fm.cwd, name)
        try:
            with open(target, "w", encoding="utf-8"):
                pass
            return f"Done. The file '{name}' has been created."
        except OSError as e:
            return f"I couldn't create '{name}': {e}"

    # delete / remove (asks first, shows the resolved path)
    m = _DELETE_RE.match(lower)
    if m:
        name = m.group(1).strip().strip("?.!\"'")
        if not name or name in ("it", "that", "this", "them"):
            return None
        fm = _fm(ctx)
        resolved, err = resolve_delete(name, fm.cwd)
        if err:
            return err
        return confirm.request("delete", f"Delete '{resolved}'?",
                               {"path": resolved, "cwd": fm.cwd})

    return None


def _walk(cwd, limit=400):
    hits = []
    for root, _, files in os.walk(cwd):
        for f in files:
            hits.append(os.path.join(root, f))
            if len(hits) >= limit:
                return hits
    return hits


def _find_kind(kind, fm):
    exts = _KINDS.get(kind)
    if exts:
        found = [p for p in _walk(fm.cwd) if p.lower().endswith(exts)]
    else:
        found = [p for p in _walk(fm.cwd) if kind in os.path.basename(p).lower()]
    if not found:
        return f"I couldn't find any {kind} files in {fm.cwd}."
    shown = found[:8]
    lines = [f"Found {len(found)} {kind} file(s):"] + [f"  {p}" for p in shown]
    if len(found) > 8:
        lines.append(f"  ...and {len(found) - 8} more.")
    return "\n".join(lines)


def _find_named(name, fm):
    found = [p for p in _walk(fm.cwd) if name.lower() in os.path.basename(p).lower()]
    if not found:
        return f"I couldn't find anything named '{name}' in {fm.cwd}."
    lines = [f"Found {len(found)} match(es):"] + [f"  {p}" for p in found[:8]]
    if len(found) > 8:
        lines.append(f"  ...and {len(found) - 8} more.")
    return "\n".join(lines)


def _find_today(fm):
    today = datetime.date.today()
    found = []
    for p in _walk(fm.cwd):
        try:
            if datetime.date.fromtimestamp(os.path.getmtime(p)) == today:
                found.append(p)
        except OSError:
            continue
        if len(found) >= 30:
            break
    if not found:
        return "No files in this folder were created or modified today."
    lines = [f"{len(found)} file(s) from today:"] + [f"  {p}" for p in found[:10]]
    if len(found) > 10:
        lines.append(f"  ...and {len(found) - 10} more.")
    return "\n".join(lines)


def _do_delete(path):
    if not path or not os.path.exists(path):
        return f"Not found: '{os.path.basename(path or '')}'."
    parent, base = os.path.dirname(path), os.path.basename(path)
    exact = exact_entry(parent, base)
    if exact is None:
        return f"Not found: '{base}'."
    if exact != base:
        return (f"Refusing: '{base}' is not the exact name "
                f"(did you mean '{exact}'?).")
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return f"Deleted '{path}'."
    except OSError as e:
        return f"I couldn't delete '{base}': {e}"
