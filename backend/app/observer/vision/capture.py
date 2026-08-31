from __future__ import annotations

from dataclasses import dataclass

import cv2
import mss
import numpy as np


@dataclass(slots=True)
class CaptureFrame:
    image_bgr: np.ndarray
    width: int
    height: int


class ScreenCapture:
    def __init__(self, monitor_index: int = 1) -> None:
        self.monitor_index = monitor_index

    def grab(self) -> CaptureFrame:
        with mss.mss() as sct:
            monitor = sct.monitors[self.monitor_index]
            raw = np.asarray(sct.grab(monitor))
            bgr = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
            return CaptureFrame(
                image_bgr=bgr,
                width=bgr.shape[1],
                height=bgr.shape[0],
            )
