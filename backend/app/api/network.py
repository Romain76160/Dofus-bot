from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.observer.network.decoder import NetworkStreamDecoder
from app.observer.network.models import (
    DecodedNetworkEvent,
    LiveCaptureHeartbeat,
)
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
    hex_data: str = Field(min_length=2, max_length=2 * 1024 * 1024)


def _decode_hex(hex_data: str) -> bytes:
    compact = "".join(hex_data.split())
    if len(compact) % 2:
        raise ValueError("hex payload must contain a whole number of bytes")
    return bytes.fromhex(compact)


async def _process_raw_chunk(
    direction: str,
    chunk: bytes,
) -> tuple[int, int, list[str], int | None]:
    packets, observations = decoder.feed(direction, chunk)

    accepted_map_id: int | None = None
    for observation in observations:
        snapshot = await store.apply(observation)
        if (
            observation.key == "map_id"
            and snapshot.map_id.value == observation.value
        ):
            accepted_map_id = int(observation.value)

    return (
        len(packets),
        len(observations),
        [packet.summary() for packet in packets[-5:]],
        accepted_map_id,
    )


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
    live_capture = await network_event_service.live_capture_status()

    return {
        "enabled": settings.network_observer_enabled,
        "profile_build": decoder.profile.build,
        "layouts": layouts,
        "decoded_ingest_enabled": True,
        "raw_replay_enabled": True,
        "messages_seen": debug.messages_seen,
        "history_size": debug.events_in_history,
        "live_capture": live_capture.model_dump(mode="json"),
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


@router.post("/live-capture/heartbeat")
async def live_capture_heartbeat(
    heartbeat: LiveCaptureHeartbeat,
):
    return await network_event_service.live_capture_heartbeat(heartbeat)


@router.get("/live-capture/status")
async def live_capture_status():
    return await network_event_service.live_capture_status()


@router.post("/replay-hex")
async def replay_hex(request: HexReplayRequest) -> dict:
    try:
        chunk = _decode_hex(request.hex_data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    packets_count, observations_count, packet_summaries, accepted_map_id = (
        await _process_raw_chunk(request.direction, chunk)
    )

    if accepted_map_id is not None:
        await network_event_service.enrich_map(accepted_map_id)

    return {
        "ok": True,
        "bytes": len(chunk),
        "packets_count": packets_count,
        "observations_count": observations_count,
        "packets": packet_summaries,
        "accepted_map_id": accepted_map_id,
    }


@router.post("/replay-batch")
async def replay_batch(
    requests: list[HexReplayRequest],
) -> dict:
    if not requests:
        return {
            "ok": True,
            "chunks": 0,
            "bytes": 0,
            "packets_count": 0,
            "observations_count": 0,
            "accepted_map_id": None,
            "last_packets": [],
        }
    if len(requests) > 500:
        raise HTTPException(
            status_code=413,
            detail="batch is limited to 500 raw chunks",
        )

    decoded: list[tuple[str, bytes]] = []
    total_bytes = 0
    max_batch_bytes = 8 * 1024 * 1024

    for index, request in enumerate(requests):
        try:
            chunk = _decode_hex(request.hex_data)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"chunk {index}: {exc}",
            ) from exc

        total_bytes += len(chunk)
        if total_bytes > max_batch_bytes:
            raise HTTPException(
                status_code=413,
                detail="raw batch exceeds 8 MiB",
            )
        decoded.append((request.direction, chunk))

    packets_count = 0
    observations_count = 0
    accepted_map_id: int | None = None
    last_packets: list[str] = []

    # Preserve capture order: the decoder owns stateful framers per direction.
    for direction, chunk in decoded:
        (
            chunk_packets,
            chunk_observations,
            packet_summaries,
            chunk_map_id,
        ) = await _process_raw_chunk(direction, chunk)
        packets_count += chunk_packets
        observations_count += chunk_observations
        if packet_summaries:
            last_packets = packet_summaries
        if chunk_map_id is not None:
            accepted_map_id = chunk_map_id

    if accepted_map_id is not None:
        await network_event_service.enrich_map(accepted_map_id)

    return {
        "ok": True,
        "chunks": len(decoded),
        "bytes": total_bytes,
        "packets_count": packets_count,
        "observations_count": observations_count,
        "accepted_map_id": accepted_map_id,
        "last_packets": last_packets,
    }
