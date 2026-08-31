from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.observer.network.decoder import NetworkStreamDecoder
from app.observer.network.models import DecodedNetworkEvent
from app.observer.network.profile import BuildProfile
from app.observer.network.service import network_event_service
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
    debug = await network_event_service.debug_state()

    return {
        "enabled": settings.network_observer_enabled,
        "profile_build": decoder.profile.build,
        "layouts": layouts,
        "decoded_ingest_enabled": True,
        "messages_seen": debug.messages_seen,
        "history_size": debug.events_in_history,
    }


@router.post("/ingest")
async def ingest_decoded_event(
    event: DecodedNetworkEvent,
):
    """Ingest one already-decoded, read-only network event."""
    return await network_event_service.ingest(event)


@router.post("/ingest-batch")
async def ingest_decoded_events(
    events: list[DecodedNetworkEvent],
) -> dict:
    if len(events) > 500:
        raise HTTPException(
            status_code=413,
            detail="batch is limited to 500 events",
        )

    applied_events = 0
    last_debug = None

    for event in events:
        last_debug = await network_event_service.ingest(event)
        if last_debug.applied:
            applied_events += 1

    return {
        "received": len(events),
        "applied_events": applied_events,
        "debug": last_debug,
    }


@router.get("/debug")
async def network_debug():
    return await network_event_service.debug_state()


@router.get("/events")
async def network_events(
    limit: int = Query(default=50, ge=1, le=100),
):
    return await network_event_service.recent_events(limit)


@router.post("/reset")
async def reset_network_debug():
    return await network_event_service.reset()


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

    accepted_map_id: int | None = None
    for observation in observations:
        snapshot = await store.apply(observation)
        if (
            observation.key == "map_id"
            and snapshot.map_id.value == observation.value
        ):
            accepted_map_id = int(observation.value)

    if accepted_map_id is not None:
        await network_event_service.enrich_map(accepted_map_id)

    return {
        "ok": True,
        "packets": [packet.summary() for packet in packets],
        "observations": [
            observation.model_dump(mode="json")
            for observation in observations
        ],
    }
