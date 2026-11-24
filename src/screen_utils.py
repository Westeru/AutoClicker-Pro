import ctypes
import os
import sys
import time
from ctypes import wintypes
from typing import Any, Dict, List, Optional, Tuple


def get_snips_dir() -> str:
    """Return a writable directory in AppData (or temp fallback) for saved snips."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        snips_dir = os.path.join(base, "AutoClickerPro", "snips")
    else:
        import tempfile
        snips_dir = os.path.join(tempfile.gettempdir(), "AutoClickerPro", "snips")
    os.makedirs(snips_dir, exist_ok=True)
    return snips_dir


def save_qimage_snip(image, prefix: str = "snip") -> Optional[str]:
    """Save a QImage or QPixmap to the AppData snips folder and return its path."""
    if image is None or image.isNull():
        return None
    snips_dir = get_snips_dir()
    filename = f"{prefix}_{int(time.time() * 1000)}.png"
    path = os.path.join(snips_dir, filename)
    if image.save(path, "PNG"):
        return path
    return None


def _get_qt_screen_names() -> Dict[Tuple[int, int], str]:
    """Map (left, top) -> friendly screen name from Qt if a QApplication is active."""
    names: Dict[Tuple[int, int], str] = {}
    try:
        from PySide6.QtGui import QGuiApplication
        app = QGuiApplication.instance()
        if app is not None:
            for screen in app.screens():
                g = screen.geometry()
                dpr = screen.devicePixelRatio() or 1.0
                phys_x = int(round(g.x() * dpr))
                phys_y = int(round(g.y() * dpr))
                names[(g.x(), g.y())] = screen.name()
                names[(phys_x, phys_y)] = screen.name()
    except Exception:
        pass
    return names


def _enum_windows_monitors() -> List[Dict[str, Any]]:
    """Enumerate physical monitor rectangles using Windows EnumDisplayMonitors."""
    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    raw_monitors: List[Dict[str, Any]] = []

    def _callback(hmon, hdc, lprc, lparam):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor
            raw_monitors.append({
                "device": mi.szDevice,
                "left": int(r.left),
                "top": int(r.top),
                "right": int(r.right),
                "bottom": int(r.bottom),
                "width": int(r.right - r.left),
                "height": int(r.bottom - r.top),
                "is_primary": bool(mi.dwFlags & 1),
            })
        return 1

    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(RECT),
        wintypes.LPARAM,
    )
    user32.EnumDisplayMonitors(0, 0, callback_type(_callback), 0)

    # Sort so primary monitor is first, then left-to-right, top-to-bottom
    raw_monitors.sort(key=lambda m: (not m["is_primary"], m["left"], m["top"]))
    return raw_monitors


def get_monitors() -> List[Dict[str, Any]]:
    """
    Return a list of selectable monitor entries.
    Index 0 is always 'All Monitors' (virtual desktop union).
    Indices 1..N are individual physical monitors.
    Each entry contains: id, name, rect (left, top, right, bottom), width, height, is_all.
    """
    qt_names = _get_qt_screen_names()
    physical: List[Dict[str, Any]] = []

    if sys.platform == "win32":
        try:
            physical = _enum_windows_monitors()
        except Exception:
            physical = []

    # Fallback to Qt screens if non-Windows or Win32 enumeration returned nothing
    if not physical:
        try:
            from PySide6.QtGui import QGuiApplication
            app = QGuiApplication.instance()
            if app is not None:
                primary = app.primaryScreen()
                for screen in app.screens():
                    g = screen.geometry()
                    physical.append({
                        "device": screen.name(),
                        "left": g.x(),
                        "top": g.y(),
                        "right": g.x() + g.width(),
                        "bottom": g.y() + g.height(),
                        "width": g.width(),
                        "height": g.height(),
                        "is_primary": (screen == primary),
                    })
        except Exception:
            pass

    if not physical:
        return [{
            "id": 0,
            "name": "All Monitors (Default)",
            "rect": None,
            "width": 0,
            "height": 0,
            "is_all": True,
        }]

    min_left = min(m["left"] for m in physical)
    min_top = min(m["top"] for m in physical)
    max_right = max(m["right"] for m in physical)
    max_bottom = max(m["bottom"] for m in physical)
    total_w = max_right - min_left
    total_h = max_bottom - min_top

    result: List[Dict[str, Any]] = [{
        "id": 0,
        "name": f"All Monitors ({total_w}×{total_h})",
        "rect": (min_left, min_top, max_right, max_bottom),
        "width": total_w,
        "height": total_h,
        "is_all": True,
    }]

    for idx, m in enumerate(physical, start=1):
        friendly = qt_names.get((m["left"], m["top"])) or m["device"].replace("\\\\.\\", "")
        primary_tag = " [Primary]" if m["is_primary"] else ""
        result.append({
            "id": idx,
            "name": f"Monitor {idx}: {friendly} ({m['width']}×{m['height']}){primary_tag}",
            "rect": (m["left"], m["top"], m["right"], m["bottom"]),
            "width": m["width"],
            "height": m["height"],
            "is_all": False,
        })

    return result
