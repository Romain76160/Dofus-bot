from __future__ import annotations

from collections.abc import AsyncIterator

from app.observer.base import Observer
from app.state.models import Observation


class NetworkObserver(Observer):
    """
    Adapter boundary for an authorized, read-only event source.

    Keep transport/protocol-specific code outside the rest of the bot:
    convert decoded events into generic Observation objects here.
    """

    async def stream(self) -> AsyncIterator[Observation]:
        if False:
            yield Observation(
                key="last_event",
                value="network observer placeholder",
                source="network",
            )
        return
