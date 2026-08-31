from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings

from .window import find_window_region


@dataclass(slots=True)
class CaptureFrame:
    image_bgr: Any
    width: int
    height: int
    window_title: str | None = None


class ScreenCapture:
    """Capture the Dofus client area; never capture the whole desktop by default."""

    def __init__(
        self,
        window_title: str | None = None,
        monitor_index: int = 1,
        allow_full_desktop_fallback: bool | None = None,
    ) -> None:
        self.window_title = window_title or settings.dofus_window_title
        self.monitor_index = monitor_index
        self.allow_full_desktop_fallback = (
            settings.vision_full_desktop_fallback
            if allow_full_desktop_fallback is None
            else allow_full_desktop_fallback
        )

    def grab(self) -> CaptureFrame:
        # Lazy imports keep the API/network observer usable even when optional
        # vision dependencies are not installed yet.
        import cv2
        import mss
        import numpy as np

        region = find_window_region(self.window_title)

        with mss.mss() as sct:
            if region is not None:
                target = {
                    "left": region.left,
                    "top": region.top,
                    "width": region.width,
                    "height": region.height,
                }
                title = region.title
            elif self.allow_full_desktop_fallback:
                target = sct.monitors[self.monitor_index]
                title = None
            else:
                raise RuntimeError(
                    f'Dofus window matching "{self.window_title}" was not found'
                )

            raw = np.asarray(sct.grab(target))
            bgr = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
            return CaptureFrame(
                image_bgr=bgr,
                width=bgr.shape[1],
                height=bgr.shape[0],
                window_title=title,
            )
