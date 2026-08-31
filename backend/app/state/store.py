from __future__ import annotations

import asyncio
from collections.abc import Callable

from .models import GameState, Observation, StateField


class StateStore:
    def __init__(self) -> None:
        self._state = GameState()
        self._lock = asyncio.Lock()
        self._subscribers: set[Callable[[GameState], None]] = set()

    async def snapshot(self) -> GameState:
        async with self._lock:
            return self._state.model_copy(deep=True)

    async def apply(self, observation: Observation) -> GameState:
        async with self._lock:
            if not hasattr(self._state, observation.key):
                raise KeyError(f"Unknown state key: {observation.key}")

            current: StateField = getattr(self._state, observation.key)

            # Newer observations win unless they are much less trustworthy.
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
