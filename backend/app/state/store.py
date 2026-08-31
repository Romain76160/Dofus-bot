from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable

from app.config import settings

from .models import GameState, Observation, StateField


class StateStore:
    def __init__(self, history_size: int | None = None) -> None:
        self._state = GameState()
        self._lock = asyncio.Lock()
        self._subscribers: set[Callable[[GameState], None]] = set()
        self._history: deque[Observation] = deque(
            maxlen=history_size or settings.observation_history_size
        )

    async def snapshot(self) -> GameState:
        async with self._lock:
            return self._state.model_copy(deep=True)

    async def history(self, limit: int = 50) -> list[Observation]:
        limit = max(1, min(limit, self._history.maxlen or limit))
        async with self._lock:
            items = list(self._history)[-limit:]
        return [item.model_copy(deep=True) for item in reversed(items)]

    async def clear_history(self) -> None:
        async with self._lock:
            self._history.clear()

    async def apply(self, observation: Observation) -> GameState:
        async with self._lock:
            if not hasattr(self._state, observation.key):
                raise KeyError(f"Unknown state key: {observation.key}")

            self._history.append(observation.model_copy(deep=True))
            current: StateField = getattr(self._state, observation.key)

            # Newer observations win unless they are materially less trustworthy.
            if (
                observation.observed_at >= current.updated_at
                and observation.confidence + 0.15 >= current.confidence
            ):
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
