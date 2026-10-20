"""Live system snapshot: CPU, RAM, disk, battery, processes."""

import os
import platform
import shutil
import time

from ..core import speaker

try:
    import psutil
except ImportError:
    psutil = None

from types import SimpleNamespace


def bar(percent: float, width: int = 20) -> str:
    try:
        filled = int(round(width * max(0.0, min(100.0, percent)) / 100.0))
    except (TypeError, ValueError):
        filled = 0
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def format_bytes(b) -> str:
    try:
        b = float(b)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or unit == "TB":
            return f"{b:.2f} {unit}"
        b /= 1024.0


def format_uptime(seconds) -> str:
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "?"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    mins, secs = divmod(seconds, 60)
    if days:
        return f"{days}d {hours}h {mins}m"
    if hours:
        return f"{hours}h {mins}m"
    if mins:
        return f"{mins}m {secs}s"
    return f"{secs}s"


def _cpu_model():
    model = platform.processor() or ""
    if model and model != "AMD64":
        return model
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                name, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                return (name or "").strip() or "CPU"
        except OSError:
            pass
    return model or "CPU"


def get_snapshot():
    if psutil:
        try:
            cpu_load = float(psutil.cpu_percent(interval=0.5))
        except Exception:
            cpu_load = 0.0
        try:
            vm = psutil.virtual_memory()
            used_mem, total_mem = int(vm.used), int(vm.total)
        except Exception:
            used_mem, total_mem = 0, 0
        try:
            du = shutil.disk_usage(os.path.expanduser("~"))
            disk = SimpleNamespace(used=du.used, total=du.total)
        except OSError:
            disk = None
        try:
            b = psutil.sensors_battery()
            battery = SimpleNamespace(
                percent=float(b.percent) if b else None,
                power_plugged=bool(b.power_plugged) if b else None)
        except Exception:
            battery = SimpleNamespace(percent=None, power_plugged=None)
        try:
            uptime = time.time() - psutil.boot_time()
        except Exception:
            uptime = 0
        cpu_count = psutil.cpu_count() or os.cpu_count() or 0
    else:
        cpu_load, used_mem, total_mem = 0.0, 0, 0
        try:
            du = shutil.disk_usage(os.path.expanduser("~"))
            disk = SimpleNamespace(used=du.used, total=du.total)
        except OSError:
            disk = None
        battery = SimpleNamespace(percent=None, power_plugged=None)
        uptime, cpu_count = 0, os.cpu_count() or 0
    return {
        "hostname": platform.node(),
        "platform": platform.system() or "OS",
        "arch": platform.machine(),
        "cpu_count": cpu_count,
        "cpu_model": _cpu_model(),
        "cpu_load": cpu_load,
        "used_mem": used_mem,
        "total_mem": total_mem,
        "disk": disk,
        "battery": battery,
        "uptime": uptime,
    }


def show(snap: dict):
    speaker.header("SYSTEM STATUS")
    speaker.line(f"Host: {snap.get('hostname')}  ({snap.get('platform')} {snap.get('arch')})")
    speaker.line(f"CPU: {snap.get('cpu_model')} x{snap.get('cpu_count')}  "
                 f"{bar(snap.get('cpu_load') or 0)} {snap.get('cpu_load') or 0:.0f}%")
    total = snap.get("total_mem") or 0
    used = snap.get("used_mem") or 0
    pct = (used / total * 100) if total else 0
    speaker.line(f"RAM: {format_bytes(used)} / {format_bytes(total)}  {bar(pct)} {pct:.0f}%")
    disk = snap.get("disk")
    if disk and disk.total:
        dpct = disk.used / disk.total * 100
        speaker.line(f"Disk: {format_bytes(disk.used)} / {format_bytes(disk.total)}  "
                     f"{bar(dpct)} {dpct:.0f}%")
    batt = snap.get("battery")
    try:
        if batt is not None and batt.percent is not None:
            speaker.line(f"Battery: {int(batt.percent)}% "
                         f"{'(charging)' if batt.power_plugged else '(on battery)'}")
    except Exception:
        pass
    speaker.line(f"Uptime: {format_uptime(snap.get('uptime') or 0)}")


def show_processes(top: int = 15):
    speaker.header(f"TOP {top} PROCESSES")
    if not psutil:
        speaker.line("Process listing needs psutil (pip install psutil).")
        return
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = p.info
                rss = info["memory_info"].rss if info.get("memory_info") else 0
                procs.append((info.get("cpu_percent") or 0, info.get("pid"),
                              info.get("name"), rss))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(reverse=True)
        for cpu, pid, name, rss in procs[:top]:
            speaker.raw(f"  {str(pid).rjust(7)}  {cpu:5.1f}%  {format_bytes(rss).rjust(10)}  {name}")
    except Exception as e:
        speaker.error_msg(str(e))
