from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


SourceName = Literal["network", "vision", "game_data", "manual", "system"]
ConflictReason = Literal[
    "older_observation",
    "lower_confidence",
    "lower_source_priority",
    "source_disagreement",
]


class Observation(BaseModel):
    key: str
    value: Any
    source: SourceName
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class StateField(BaseModel):
    value: Any = None
    source: SourceName = "system"
    confidence: float = 0.0
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ConflictRecord(BaseModel):
    key: str
    current_value: Any
    current_source: SourceName
    current_confidence: float
    incoming_value: Any
    incoming_source: SourceName
    incoming_confidence: float
    observed_at: datetime
    reason: ConflictReason
    accepted: bool


class GameState(BaseModel):
    map_id: StateField = Field(default_factory=StateField)
    player_cell: StateField = Field(default_factory=StateField)
    in_fight: StateField = Field(default_factory=StateField)
    my_turn: StateField = Field(default_factory=StateField)
    popup_visible: StateField = Field(default_factory=StateField)
    interactives: StateField = Field(
        default_factory=lambda: StateField(value=[])
    )
    network_connected: StateField = Field(
        default_factory=lambda: StateField(value=False)
    )
    last_event: StateField = Field(default_factory=StateField)
