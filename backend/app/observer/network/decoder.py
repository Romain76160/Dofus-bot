from __future__ import annotations

from dataclasses import dataclass

from app.state.models import Observation

from .frame import GameFrame, parse_game_frame, try_parse_any
from .framer import StreamFramer
from .profile import BuildProfile
from .protobuf_wire import ProtobufDecodeError


@dataclass(slots=True)
class DecodedPacket:
    direction: str
    kind: str
    message_id: int
    wire_key: str | None
    type_url: str | None
    payload: bytes

    def summary(self) -> dict:
        return {
            "direction": self.direction,
            "kind": self.kind,
            "message_id": self.message_id,
            "wire_key": self.wire_key,
            "type_url": self.type_url,
            "payload_size": len(self.payload),
        }


class NetworkStreamDecoder:
    def __init__(self, profile: BuildProfile | None = None) -> None:
        self._framers = {
            "client_to_server": StreamFramer(),
            "server_to_client": StreamFramer(),
        }
        self.profile = profile or BuildProfile()

    def feed(
        self,
        direction: str,
        chunk: bytes,
    ) -> tuple[list[DecodedPacket], list[Observation]]:
        if direction not in self._framers:
            raise ValueError(f"unknown direction: {direction}")

        packets: list[DecodedPacket] = []
        observations: list[Observation] = []

        for body in self._framers[direction].feed(chunk):
            try:
                frame: GameFrame = parse_game_frame(body)
            except ProtobufDecodeError:
                continue

            any_envelope = try_parse_any(frame.payload.data)
            payload = any_envelope.value if any_envelope else frame.payload.data
            wire_key = any_envelope.wire_key if any_envelope else None

            packet = DecodedPacket(
                direction=direction,
                kind=frame.kind,
                message_id=frame.payload.message_id,
                wire_key=wire_key,
                type_url=any_envelope.type_url if any_envelope else None,
                payload=payload,
            )
            packets.append(packet)

            observations.append(
                Observation(
                    key="last_event",
                    value=packet.summary(),
                    source="network",
                    confidence=1.0,
                )
            )

            if wire_key:
                observations.extend(
                    self.profile.observations_for(wire_key, payload)
                )

        return packets, observations
