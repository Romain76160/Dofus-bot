from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Direction = Literal["client_to_server", "server_to_client", "unknown"]


class DecodedNetworkEvent(BaseModel):
    """Transport-neutral event emitted by a read-only external decoder."""

    message_type: str = "unknown"
    direction: Direction = "unknown"
    payload: dict[str, Any] = Field(default_factory=dict)
    wire_key: str | None = None
    captured_at: datetime | None = None


class Candidate(BaseModel):
    semantic: Literal["map_id", "player_cell", "cell_id"]
    path: str
    value: int
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    auto_apply: bool = False


class NetworkDebugState(BaseModel):
    messages_seen: int = 0
    events_in_history: int = 0
    last_message_type: str | None = None
    last_wire_key: str | None = None
    last_direction: Direction = "unknown"
    candidates: list[Candidate] = Field(default_factory=list)
    applied: dict[str, int] = Field(default_factory=dict)
    ambiguous_candidates: int = 0
