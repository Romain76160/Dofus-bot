from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.state.models import Observation


class Observer(ABC):
    @abstractmethod
    async def stream(self) -> AsyncIterator[Observation]:
        """Yield normalized observations from one source."""
        raise NotImplementedError
