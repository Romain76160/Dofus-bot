from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def match_template(
    frame: np.ndarray,
    template_path: str | Path,
    threshold: float = 0.85,
) -> tuple[bool, float, tuple[int, int] | None]:
    template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if template is None:
        return False, 0.0, None

    result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, location = cv2.minMaxLoc(result)

    if confidence < threshold:
        return False, float(confidence), None

    h, w = template.shape[:2]
    center = (location[0] + w // 2, location[1] + h // 2)
    return True, float(confidence), center
