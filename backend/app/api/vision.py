from __future__ import annotations

import importlib.util
import platform

from fastapi import APIRouter

from app.config import settings
from app.observer.vision.window import find_window_region

router = APIRouter(prefix="/api/vision", tags=["vision"])


@router.get("/status")
async def vision_status() -> dict:
    region = (
        find_window_region(settings.dofus_window_title)
        if settings.vision_enabled
        else None
    )
    return {
        "enabled": settings.vision_enabled,
        "platform": platform.system(),
        "window_title_query": settings.dofus_window_title,
        "window_found": region is not None,
        "region": region.as_dict() if region else None,
        "capture_dependency_ready": importlib.util.find_spec("mss") is not None,
        "opencv_dependency_ready": importlib.util.find_spec("cv2") is not None,
        "full_desktop_fallback": settings.vision_full_desktop_fallback,
    }
