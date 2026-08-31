from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings
from app.observer.network.decoder import NetworkStreamDecoder
from app.observer.network.profile import BuildProfile
from app.state.store import store

router = APIRouter(prefix="/api/network", tags=["network"])


def _load_profile() -> BuildProfile:
    path = Path(settings.network_profile_path)
    if path.exists():
        return BuildProfile.load(path)
    return BuildProfile()


decoder = NetworkStreamDecoder(profile=_load_profile())


class HexReplayRequest(BaseModel):
    direction: str = Field(
        pattern="^(client_to_server|server_to_client)$"
    )
    hex_data: str


@router.get("/status")
async def network_status() -> dict:
    layouts = {
        direction: (
            None
            if framer.layout is None
            else {
                "header": framer.layout.header.value,
                "includes_self": framer.layout.includes_self,
                "lead_skip": framer.layout.lead_skip,
            }
        )
        for direction, framer in decoder._framers.items()
    }

    return {
        "enabled": settings.network_observer_enabled,
        "profile_build": decoder.profile.build,
        "layouts": layouts,
    }


@router.post("/replay-hex")
async def replay_hex(request: HexReplayRequest) -> dict:
    compact = "".join(request.hex_data.split())

    try:
        chunk = bytes.fromhex(compact)
    except ValueError as exc:
        return {
            "ok": False,
            "error": f"invalid hex payload: {exc}",
        }

    packets, observations = decoder.feed(request.direction, chunk)

    for observation in observations:
        await store.apply(observation)

    return {
        "ok": True,
        "packets": [packet.summary() for packet in packets],
        "observations": [
            observation.model_dump(mode="json")
            for observation in observations
        ],
    }
