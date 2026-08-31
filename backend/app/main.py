from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.api.diagnostics import router as diagnostics_router
from app.api.game_data import router as game_data_router
from app.api.network import router as network_router
from app.api.vision import router as vision_router
from app.api.ws import router as ws_router
from app.config import settings
from app.observer.network.service import network_event_service
from app.state.models import Observation
from app.state.store import store

app = FastAPI(title="Dofus Hybrid Observer", version="0.7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)
app.include_router(game_data_router)
app.include_router(network_router)
app.include_router(vision_router)
app.include_router(diagnostics_router)


@app.get("/health")
async def health() -> dict:
    diagnostics = await store.diagnostics()
    live_capture = await network_event_service.live_capture_status()
    return {
        "status": "ok",
        "version": "0.7.0",
        "vision_enabled": settings.vision_enabled,
        "network_observer_enabled": settings.network_observer_enabled,
        "allow_input": settings.allow_input,
        "live_capture_active": live_capture.active,
        "stale_fields": diagnostics["stale_fields"],
        "conflict_count": diagnostics["conflict_count"],
    }


@app.get("/api/state")
async def get_state():
    return await store.snapshot()


@app.get("/api/observations")
async def observation_history(
    limit: int = Query(default=50, ge=1, le=200),
):
    return await store.history(limit)


@app.post("/api/debug/observation")
async def push_debug_observation(observation: Observation):
    return await store.apply(observation)
