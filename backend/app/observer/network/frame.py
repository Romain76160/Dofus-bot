from __future__ import annotations

from dataclasses import dataclass

from .protobuf_wire import (
    ProtobufDecodeError,
    WireType,
    first_field,
)


@dataclass(slots=True)
class FramePayload:
    message_id: int
    data: bytes


@dataclass(slots=True)
class GameFrame:
    kind: str
    payload: FramePayload
    correlation_id: int | None = None
    status: int | None = None


@dataclass(slots=True)
class AnyEnvelope:
    type_url: str
    value: bytes

    @property
    def wire_key(self) -> str:
        return self.type_url.rsplit("/", 1)[-1]


def _parse_payload(data: bytes) -> FramePayload:
    id_field = first_field(data, 1)
    body_field = first_field(data, 2)

    if (
        id_field is None
        or id_field.wire_type is not WireType.VARINT
        or not isinstance(id_field.value, int)
    ):
        raise ProtobufDecodeError("frame payload has no numeric id")

    if (
        body_field is None
        or body_field.wire_type is not WireType.LEN
        or not isinstance(body_field.value, bytes)
    ):
        raise ProtobufDecodeError("frame payload has no data bytes")

    return FramePayload(message_id=id_field.value, data=body_field.value)


def parse_game_frame(data: bytes) -> GameFrame:
    root = first_field(data, 1) or first_field(data, 2) or first_field(data, 3)

    if root is None or root.wire_type is not WireType.LEN or not isinstance(root.value, bytes):
        raise ProtobufDecodeError("not a recognized game frame")

    # Request
    request = first_field(data, 1)
    if request is not None:
        inner = request.value
        assert isinstance(inner, bytes)
        correlation = first_field(inner, 1)
        payload = first_field(inner, 2)

        if payload is None or payload.wire_type is not WireType.LEN:
            raise ProtobufDecodeError("request payload missing")

        return GameFrame(
            kind="request",
            correlation_id=int(correlation.value) if correlation else None,
            payload=_parse_payload(payload.value),
        )

    # Response
    response = first_field(data, 2)
    if response is not None:
        inner = response.value
        assert isinstance(inner, bytes)
        correlation = first_field(inner, 1)
        status = first_field(inner, 2)
        payload = first_field(inner, 3)

        if payload is None or payload.wire_type is not WireType.LEN:
            raise ProtobufDecodeError("response payload missing")

        return GameFrame(
            kind="response",
            correlation_id=int(correlation.value) if correlation else None,
            status=int(status.value) if status else None,
            payload=_parse_payload(payload.value),
        )

    # Event
    event = first_field(data, 3)
    assert event is not None and isinstance(event.value, bytes)
    return GameFrame(kind="event", payload=_parse_payload(event.value))


def try_parse_any(data: bytes) -> AnyEnvelope | None:
    type_field = first_field(data, 1)
    value_field = first_field(data, 2)

    if (
        type_field is None
        or value_field is None
        or type_field.wire_type is not WireType.LEN
        or value_field.wire_type is not WireType.LEN
        or not isinstance(type_field.value, bytes)
        or not isinstance(value_field.value, bytes)
    ):
        return None

    try:
        type_url = type_field.value.decode("utf-8")
    except UnicodeDecodeError:
        return None

    if "/" not in type_url:
        return None

    return AnyEnvelope(type_url=type_url, value=value_field.value)
