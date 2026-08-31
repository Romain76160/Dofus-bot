from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.game_data import router as game_data_router
from app.api.network import router as network_router
from app.api.ws import router as ws_router
from app.config import settings
from app.state.models import Observation
from app.state.store import store

app = FastAPI(title="Dofus Hybrid Observer", version="0.2.0")

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


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "vision_enabled": settings.vision_enabled,
        "network_observer_enabled": settings.network_observer_enabled,
        "allow_input": settings.allow_input,
    }


@app.get("/api/state")
async def get_state():
    return await store.snapshot()


@app.post("/api/debug/observation")
async def push_debug_observation(observation: Observation):
    return await store.apply(observation)
