from fastapi import APIRouter, Query

from app.config import settings
from app.state.store import store

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/health")
async def diagnostics_health(
    stale_after_seconds: float | None = Query(
        default=None,
        gt=0,
        le=3600,
    ),
):
    return await store.diagnostics(stale_after_seconds)


@router.get("/conflicts")
async def diagnostics_conflicts(
    limit: int = Query(default=50, ge=1, le=100),
):
    return await store.conflicts(limit)


@router.get("/fusion-policy")
async def fusion_policy() -> dict:
    return {
        "source_priority_penalty": settings.source_priority_penalty,
        "source_priority": settings.state_source_priority,
    }


@router.post("/reset")
async def reset_diagnostics() -> dict:
    await store.clear_diagnostics()
    return {"ok": True}
