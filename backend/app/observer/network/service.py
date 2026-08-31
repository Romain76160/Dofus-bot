from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone

from app.config import settings
from app.observer.game_data.repository import GameDataRepository
from app.state.models import Observation
from app.state.store import store

from .discovery import discover_candidates
from .models import (
    DecodedNetworkEvent,
    LiveCaptureHeartbeat,
    LiveCaptureStatus,
    NetworkDebugState,
)


class NetworkEventService:
    """Map decoded read-only events into the semantic GameState."""

    def __init__(self, history_size: int | None = None) -> None:
        self._lock = asyncio.Lock()
        self._debug = NetworkDebugState()
        self._history: deque[DecodedNetworkEvent] = deque(
            maxlen=history_size or settings.network_history_size
        )
        self._repository = GameDataRepository(settings.game_data_db_path)
        self._live_capture = LiveCaptureStatus()

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _observed_at(cls, event: DecodedNetworkEvent) -> datetime:
        observed_at = event.captured_at or datetime.now(timezone.utc)
        return cls._aware(observed_at)

    async def _apply_interactives(self, map_id: int) -> int:
        rows = self._repository.interactions_for_map(map_id)
        normalized = [
            {
                "map_id": row.get("mapId"),
                "world_id": row.get("worldId"),
                "gfx_id": row.get("gfxId"),
                "cell_id": row.get("cellId"),
                "interaction_id": row.get("interactionId"),
            }
            for row in rows
        ]
        await store.apply(
            Observation(
                key="interactives",
                value=normalized,
                source="game_data",
                confidence=1.0,
            )
        )
        return len(normalized)

    async def enrich_map(self, map_id: int) -> int:
        return await self._apply_interactives(map_id)

    async def ingest(self, event: DecodedNetworkEvent) -> NetworkDebugState:
        candidates = discover_candidates(event.payload)
        observed_at = self._observed_at(event)
        applied: dict[str, int] = {}

        await store.apply(
            Observation(
                key="network_connected",
                value=True,
                source="network",
                confidence=1.0,
                observed_at=observed_at,
            )
        )

        await store.apply(
            Observation(
                key="last_event",
                value={
                    "message_type": event.message_type,
                    "direction": event.direction,
                    "wire_key": event.wire_key,
                    "payload": event.payload,
                },
                source="network",
                confidence=1.0,
                observed_at=observed_at,
            )
        )

        for semantic in ("map_id", "player_cell"):
            best = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.semantic == semantic and candidate.auto_apply
                ),
                None,
            )
            if best is None:
                continue

            await store.apply(
                Observation(
                    key=semantic,
                    value=best.value,
                    source="network",
                    confidence=best.confidence,
                    observed_at=observed_at,
                )
            )
            snapshot = await store.snapshot()
            if getattr(snapshot, semantic).value == best.value:
                applied[semantic] = best.value

        if "map_id" in applied:
            await self._apply_interactives(applied["map_id"])

        async with self._lock:
            self._history.append(event)
            self._debug.messages_seen += 1
            self._debug.events_in_history = len(self._history)
            self._debug.last_message_type = event.message_type
            self._debug.last_wire_key = event.wire_key
            self._debug.last_direction = event.direction
            self._debug.candidates = candidates
            self._debug.applied = applied
            self._debug.ambiguous_candidates = sum(
                1 for candidate in candidates if not candidate.auto_apply
            )
            return self._debug.model_copy(deep=True)

    async def live_capture_heartbeat(
        self,
        heartbeat: LiveCaptureHeartbeat,
    ) -> LiveCaptureStatus:
        now = datetime.now(timezone.utc)
        reported_at = self._aware(heartbeat.sent_at)
        started_at = self._aware(heartbeat.started_at)

        async with self._lock:
            self._live_capture = LiveCaptureStatus(
                active=True,
                session_id=heartbeat.session_id,
                server_host=heartbeat.server_host,
                resolved_addresses=heartbeat.resolved_addresses,
                server_port=heartbeat.server_port,
                capture_filter=heartbeat.capture_filter,
                capture_mode=heartbeat.capture_mode,
                platform=heartbeat.platform,
                tool_version=heartbeat.tool_version,
                started_at=started_at,
                reported_at=reported_at,
                last_heartbeat_at=now,
                heartbeat_age_seconds=0.0,
                packets_seen=heartbeat.packets_seen,
                payload_packets=heartbeat.payload_packets,
                chunks_forwarded=heartbeat.chunks_forwarded,
                bytes_forwarded=heartbeat.bytes_forwarded,
                duplicates_skipped=heartbeat.duplicates_skipped,
                queue_drops=heartbeat.queue_drops,
                forward_errors=heartbeat.forward_errors,
                last_error=heartbeat.last_error,
            )
            status = self._live_capture.model_copy(deep=True)

        await store.apply(
            Observation(
                key="network_connected",
                value=True,
                source="network",
                confidence=1.0,
                observed_at=now,
            )
        )
        return status

    async def live_capture_status(self) -> LiveCaptureStatus:
        now = datetime.now(timezone.utc)

        async with self._lock:
            status = self._live_capture.model_copy(deep=True)
            if status.last_heartbeat_at is None:
                return status

            last_heartbeat_at = self._aware(status.last_heartbeat_at)
            age = max(0.0, (now - last_heartbeat_at).total_seconds())
            status.heartbeat_age_seconds = round(age, 3)
            status.active = age <= settings.live_capture_heartbeat_ttl_seconds
            return status

    async def recent_events(self, limit: int = 50) -> list[dict]:
        limit = max(1, min(limit, self._history.maxlen or limit))
        async with self._lock:
            events = list(self._history)[-limit:]
        return [event.model_dump(mode="json") for event in reversed(events)]

    async def debug_state(self) -> NetworkDebugState:
        async with self._lock:
            return self._debug.model_copy(deep=True)

    async def reset(self) -> NetworkDebugState:
        async with self._lock:
            self._history.clear()
            self._debug = NetworkDebugState()
            return self._debug.model_copy(deep=True)


network_event_service = NetworkEventService()
