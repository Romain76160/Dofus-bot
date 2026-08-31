from __future__ import annotations

from dataclasses import asdict, dataclass
import platform


@dataclass(slots=True)
class WindowRegion:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int

    def as_dict(self) -> dict:
        return asdict(self)


def _windows_region(title_fragment: str) -> WindowRegion | None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    matches: list[tuple[int, str]] = []
    wnd_enum_proc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    @wnd_enum_proc
    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True

        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if title_fragment.casefold() in title.casefold():
            matches.append((int(hwnd), title))
        return True

    user32.EnumWindows(enum_proc, 0)
    if not matches:
        return None

    regions: list[WindowRegion] = []
    for hwnd, title in matches:
        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            continue

        point = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
            continue

        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            continue

        regions.append(
            WindowRegion(
                hwnd=hwnd,
                title=title,
                left=int(point.x),
                top=int(point.y),
                width=width,
                height=height,
            )
        )

    return max(regions, key=lambda region: region.width * region.height, default=None)


def find_window_region(title_fragment: str) -> WindowRegion | None:
    """Return the visible Dofus client-area region on Windows."""
    if platform.system() != "Windows":
        return None
    return _windows_region(title_fragment)
