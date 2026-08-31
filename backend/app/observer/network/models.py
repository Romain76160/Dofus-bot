from __future__ import annotations

from datetime import datetime, timezone
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


class LiveCaptureHeartbeat(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    server_host: str | None = Field(default=None, max_length=255)
    resolved_addresses: list[str] = Field(default_factory=list)
    server_port: int = Field(ge=1, le=65535)
    capture_filter: str = Field(min_length=1, max_length=2048)
    capture_mode: str = "windivert_sniff"
    platform: str
    tool_version: str
    started_at: datetime
    sent_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    packets_seen: int = Field(default=0, ge=0)
    payload_packets: int = Field(default=0, ge=0)
    chunks_forwarded: int = Field(default=0, ge=0)
    bytes_forwarded: int = Field(default=0, ge=0)
    duplicates_skipped: int = Field(default=0, ge=0)
    queue_drops: int = Field(default=0, ge=0)
    forward_errors: int = Field(default=0, ge=0)
    last_error: str | None = Field(default=None, max_length=2000)


class LiveCaptureStatus(BaseModel):
    active: bool = False
    session_id: str | None = None
    server_host: str | None = None
    resolved_addresses: list[str] = Field(default_factory=list)
    server_port: int | None = None
    capture_filter: str | None = None
    capture_mode: str | None = None
    platform: str | None = None
    tool_version: str | None = None
    started_at: datetime | None = None
    reported_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    heartbeat_age_seconds: float | None = None
    packets_seen: int = 0
    payload_packets: int = 0
    chunks_forwarded: int = 0
    bytes_forwarded: int = 0
    duplicates_skipped: int = 0
    queue_drops: int = 0
    forward_errors: int = 0
    last_error: str | None = None
