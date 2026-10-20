import os
import re

from ..core import speaker
from .system import format_bytes


def exact_entry(parent, name):
    """Exact-case entry in parent matching name case-insensitively.

    Returns (exact_name or None). On Windows 'Jarvis' and 'jarvis' are the
    same object - this helper exposes which one really exists so callers
    never act on a case-variantsurprise.
    """
    try:
        entries = os.listdir(parent)
    except OSError:
        return None
    if name in entries:
        return name
    low = name.lower()
    for e in entries:
        if e.lower() == low:
            return e
    return None


class FileManager:
    def __init__(self):
        self.cwd = os.getcwd()

    def list(self):
        try:
            items = sorted(os.listdir(self.cwd))
        except OSError as e:
            speaker.error_msg(str(e))
            return
        if not items:
            speaker.line("(directory is empty)")
            return
        speaker.line(f"Location: {self.cwd}")
        dirs = [i for i in items if os.path.isdir(os.path.join(self.cwd, i))]
        files = [i for i in items if not os.path.isdir(os.path.join(self.cwd, i))]
        pad = max(len(n) for n in items) if items else 1
        for d in dirs:
            speaker.raw(
                f"  {speaker.CYAN}{speaker.BOLD}{('/' + d).ljust(pad + 2)}{speaker.RESET}{speaker.GRAY}directory{speaker.RESET}"
            )
        for f in files:
            try:
                size = format_bytes(os.path.getsize(os.path.join(self.cwd, f)))
            except OSError:
                size = ""
            speaker.raw(f"  {f.ljust(pad + 2)}{speaker.GRAY}{size}{speaker.RESET}")

    def navigate(self, path=""):
        if not path:
            speaker.raw(self.cwd)
            return
        target = os.path.abspath(os.path.join(self.cwd, path))
        if not os.path.isdir(target):
            speaker.error_msg(f"No such directory: {path}")
            return
        self.cwd = target
        speaker.success_msg(f"Now in {target}")

    def create(self, name, kind="file"):
        if not name:
            speaker.error_msg("Provide a name.")
            return
        hit = exact_entry(self.cwd, os.path.basename(name.rstrip("/\\")))
        if hit is not None and hit != os.path.basename(name.rstrip("/\\")):
            speaker.error_msg(
                f"'{name}' collides with existing '{hit}' "
                "(Windows names are case-insensitive).")
            return
        target = os.path.join(self.cwd, name)
        try:
            if kind == "dir" or name.endswith("/") or name.endswith("\\"):
                os.makedirs(target, exist_ok=True)
                speaker.success_msg(f"Directory created: {name}")
            else:
                with open(target, "w", encoding="utf-8"):
                    pass
                speaker.success_msg(f"File created: {name}")
        except OSError as e:
            speaker.error_msg(str(e))

    def _safe_target(self, name):
        """Resolve inside cwd; refuse escapes, the cwd itself, and
        case-variant surprises (exact-case match required)."""
        if not name:
            return None, "Provide a name."
        base = os.path.basename(name.rstrip("/\\"))
        if not base or base in (".", ".."):
            return None, f"Refusing to delete '{name}'."
        target = os.path.abspath(os.path.join(self.cwd, name))
        root = os.path.abspath(self.cwd)
        if target == root or not target.startswith(root + os.sep):
            return None, "Refusing to delete outside the working folder."
        exact = exact_entry(os.path.dirname(target), base)
        if exact is None:
            return None, f"Not found: {name}"
        if exact != base:
            return None, (f"No exact match for '{name}'. Did you mean '{exact}'? "
                           "Use the exact name - Windows treats them as the same file.")
        return os.path.join(os.path.dirname(target), exact), ""

    def remove(self, name):
        target, err = self._safe_target(name)
        if err:
            speaker.error_msg(err)
            return
        if not os.path.exists(target):
            speaker.error_msg(f"Not found: {name}")
            return
        try:
            if os.path.isdir(target):
                import shutil

                shutil.rmtree(target)
            else:
                os.remove(target)
            speaker.success_msg(f"Removed: {name}")
        except OSError as e:
            speaker.error_msg(str(e))

    def copy(self, src, dest):
        if not src or not dest:
            speaker.error_msg("Usage: copy <src> <dest>")
            return
        import shutil

        try:
            shutil.copy2(
                os.path.join(self.cwd, src), os.path.join(self.cwd, dest)
            )
            speaker.success_msg(f"Copied {src} -> {dest}")
        except OSError as e:
            speaker.error_msg(str(e))

    def move(self, src, dest):
        if not src or not dest:
            speaker.error_msg("Usage: move <src> <dest>")
            return
        import shutil

        try:
            shutil.move(
                os.path.join(self.cwd, src), os.path.join(self.cwd, dest)
            )
            speaker.success_msg(f"Moved {src} -> {dest}")
        except OSError as e:
            speaker.error_msg(str(e))

    def search(self, pattern):
        if not pattern:
            speaker.error_msg("Provide a search pattern.")
            return
        speaker.line(f'Searching for "{pattern}" in {self.cwd}...')
        results = []
        if "*" in pattern or "?" in pattern:
            import fnmatch
            try:
                regex = re.compile(fnmatch.translate(pattern), re.IGNORECASE)
            except re.error:
                regex = None
        else:
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                regex = None
        for root, dirs, files in os.walk(self.cwd):
            for name in dirs + files:
                if regex:
                    match = bool(regex.search(name))
                else:
                    match = pattern.lower() in name.lower()
                if match:
                    results.append(os.path.join(root, name))
        if not results:
            speaker.line("No matches found.")
            return
        for r in results[:50]:
            speaker.raw(f"  {speaker.GRAY}{r}{speaker.RESET}")
        if len(results) > 50:
            speaker.warn_msg(f"...and {len(results) - 50} more")
