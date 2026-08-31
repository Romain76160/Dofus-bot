from __future__ import annotations

import asyncio
from collections import Counter, deque
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.config import settings

from .models import ConflictRecord, GameState, Observation, SourceName, StateField


class StateStore:
    def __init__(
        self,
        history_size: int | None = None,
        conflict_history_size: int | None = None,
    ) -> None:
        self._state = GameState()
        self._lock = asyncio.Lock()
        self._subscribers: set[Callable[[GameState], None]] = set()
        self._history: deque[Observation] = deque(
            maxlen=history_size or settings.observation_history_size
        )
        self._conflicts: deque[ConflictRecord] = deque(
            maxlen=conflict_history_size or settings.conflict_history_size
        )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _priority_order(key: str) -> list[SourceName]:
        return settings.state_source_priority.get(
            key,
            settings.state_source_priority.get(
                "*",
                ["manual", "network", "vision", "game_data", "system"],
            ),
        )

    @classmethod
    def _source_rank(cls, key: str, source: SourceName) -> int:
        order = cls._priority_order(key)
        try:
            return order.index(source)
        except ValueError:
            return len(order)

    @classmethod
    def _should_accept(
        cls,
        key: str,
        current: StateField,
        observation: Observation,
    ) -> tuple[bool, str]:
        # Empty/system fields are placeholders, not real observations. The
        # first valid observation must be able to populate them even when
        # replaying historical captures.
        if current.source == "system":
            return True, "source_disagreement"

        incoming_at = cls._aware(observation.observed_at)
        current_at = cls._aware(current.updated_at)
        if incoming_at < current_at:
            return False, "older_observation"

        incoming_rank = cls._source_rank(key, observation.source)
        current_rank = cls._source_rank(key, current.source)
        penalty = settings.source_priority_penalty

        if incoming_rank < current_rank:
            if observation.confidence + penalty < current.confidence:
                return False, "lower_confidence"
            return True, "source_disagreement"

        if incoming_rank > current_rank:
            if observation.confidence < min(1.0, current.confidence + penalty):
                return False, "lower_source_priority"
            return True, "source_disagreement"

        if observation.confidence + penalty < current.confidence:
            return False, "lower_confidence"

        return True, "source_disagreement"

    async def snapshot(self) -> GameState:
        async with self._lock:
            return self._state.model_copy(deep=True)

    async def history(self, limit: int = 50) -> list[Observation]:
        limit = max(1, min(limit, self._history.maxlen or limit))
        async with self._lock:
            items = list(self._history)[-limit:]
        return [item.model_copy(deep=True) for item in reversed(items)]

    async def conflicts(self, limit: int = 50) -> list[ConflictRecord]:
        limit = max(1, min(limit, self._conflicts.maxlen or limit))
        async with self._lock:
            items = list(self._conflicts)[-limit:]
        return [item.model_copy(deep=True) for item in reversed(items)]

    async def diagnostics(
        self,
        stale_after_seconds: float | None = None,
    ) -> dict[str, Any]:
        stale_after = stale_after_seconds or settings.state_stale_after_seconds
        now = datetime.now(timezone.utc)

        async with self._lock:
            state = self._state.model_copy(deep=True)
            history = [item.model_copy(deep=True) for item in self._history]
            conflicts = [
                item.model_copy(deep=True) for item in self._conflicts
            ]

        fields: dict[str, Any] = {}
        stale_fields: list[str] = []
        for key in GameState.model_fields:
            current: StateField = getattr(state, key)
            age_seconds = max(
                0.0,
                (now - self._aware(current.updated_at)).total_seconds(),
            )
            stale = current.source == "system" or age_seconds > stale_after
            if stale:
                stale_fields.append(key)

            fields[key] = {
                "source": current.source,
                "confidence": current.confidence,
                "updated_at": current.updated_at,
                "age_seconds": round(age_seconds, 3),
                "stale": stale,
                "has_value": current.value is not None,
                "priority_rank": self._source_rank(key, current.source),
            }

        counts = Counter(item.source for item in history)
        latest_by_source: dict[str, datetime] = {}
        for item in history:
            observed_at = self._aware(item.observed_at)
            previous = latest_by_source.get(item.source)
            if previous is None or observed_at > previous:
                latest_by_source[item.source] = observed_at

        sources = {
            source: {
                "observation_count": int(counts.get(source, 0)),
                "last_observed_at": latest_by_source.get(source),
                "age_seconds": (
                    round(
                        max(
                            0.0,
                            (
                                now - latest_by_source[source]
                            ).total_seconds(),
                        ),
                        3,
                    )
                    if source in latest_by_source
                    else None
                ),
            }
            for source in ("network", "vision", "game_data", "manual", "system")
        }

        return {
            "generated_at": now,
            "stale_after_seconds": stale_after,
            "stale_fields": stale_fields,
            "healthy_fields": [
                key for key in GameState.model_fields if key not in stale_fields
            ],
            "fields": fields,
            "sources": sources,
            "observation_count": len(history),
            "conflict_count": len(conflicts),
            "rejected_conflict_count": sum(
                1 for conflict in conflicts if not conflict.accepted
            ),
            "fusion_policy": {
                "source_priority_penalty": settings.source_priority_penalty,
                "source_priority": settings.state_source_priority,
            },
        }

    async def clear_history(self) -> None:
        async with self._lock:
            self._history.clear()

    async def clear_diagnostics(self) -> None:
        async with self._lock:
            self._history.clear()
            self._conflicts.clear()

    async def apply(self, observation: Observation) -> GameState:
        async with self._lock:
            if not hasattr(self._state, observation.key):
                raise KeyError(f"Unknown state key: {observation.key}")

            observation = observation.model_copy(
                update={"observed_at": self._aware(observation.observed_at)}
            )
            self._history.append(observation.model_copy(deep=True))
            current: StateField = getattr(self._state, observation.key)

            accepted, reason = self._should_accept(
                observation.key,
                current,
                observation,
            )
            values_disagree = (
                current.source != "system"
                and current.value != observation.value
                and current.source != observation.source
            )

            if values_disagree:
                self._conflicts.append(
                    ConflictRecord(
                        key=observation.key,
                        current_value=current.value,
                        current_source=current.source,
                        current_confidence=current.confidence,
                        incoming_value=observation.value,
                        incoming_source=observation.source,
                        incoming_confidence=observation.confidence,
                        observed_at=observation.observed_at,
                        reason=reason,
                        accepted=accepted,
                    )
                )

            if accepted:
                setattr(
                    self._state,
                    observation.key,
                    StateField(
                        value=observation.value,
                        source=observation.source,
                        confidence=observation.confidence,
                        updated_at=observation.observed_at,
                    ),
                )

            return self._state.model_copy(deep=True)


store = StateStore()
