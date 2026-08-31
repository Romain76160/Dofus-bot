from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone

from app.config import settings
from app.observer.game_data.repository import GameDataRepository
from app.state.models import Observation
from app.state.store import store

from .discovery import discover_candidates
from .models import DecodedNetworkEvent, NetworkDebugState


class NetworkEventService:
    """Map decoded read-only events into the semantic GameState."""

    def __init__(self, history_size: int | None = None) -> None:
        self._lock = asyncio.Lock()
        self._debug = NetworkDebugState()
        self._history: deque[DecodedNetworkEvent] = deque(
            maxlen=history_size or settings.network_history_size
        )
        self._repository = GameDataRepository(settings.game_data_db_path)

    @staticmethod
    def _observed_at(event: DecodedNetworkEvent) -> datetime:
        observed_at = event.captured_at or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        return observed_at

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
