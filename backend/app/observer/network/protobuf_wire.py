from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class WireType(IntEnum):
    VARINT = 0
    FIXED64 = 1
    LEN = 2
    FIXED32 = 5


@dataclass(slots=True)
class WireField:
    number: int
    wire_type: WireType
    value: int | bytes


class ProtobufDecodeError(ValueError):
    pass


def read_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    value = 0
    shift = 0

    for index in range(offset, min(len(data), offset + 10)):
        byte = data[index]
        value |= (byte & 0x7F) << shift

        if byte & 0x80 == 0:
            return value, index + 1

        shift += 7

    raise ProtobufDecodeError("invalid or incomplete varint")


def parse_fields(data: bytes) -> list[WireField]:
    fields: list[WireField] = []
    offset = 0

    while offset < len(data):
        tag, offset = read_varint(data, offset)
        number = tag >> 3
        raw_wire_type = tag & 0x07

        if number <= 0:
            raise ProtobufDecodeError("protobuf field number must be positive")

        try:
            wire_type = WireType(raw_wire_type)
        except ValueError as exc:
            raise ProtobufDecodeError(
                f"unsupported protobuf wire type: {raw_wire_type}"
            ) from exc

        if wire_type is WireType.VARINT:
            value, offset = read_varint(data, offset)
            fields.append(WireField(number, wire_type, value))
            continue

        if wire_type is WireType.LEN:
            size, offset = read_varint(data, offset)
            end = offset + size
            if end > len(data):
                raise ProtobufDecodeError("truncated length-delimited field")
            fields.append(WireField(number, wire_type, data[offset:end]))
            offset = end
            continue

        if wire_type is WireType.FIXED64:
            end = offset + 8
            if end > len(data):
                raise ProtobufDecodeError("truncated fixed64 field")
            value = int.from_bytes(data[offset:end], "little")
            fields.append(WireField(number, wire_type, value))
            offset = end
            continue

        if wire_type is WireType.FIXED32:
            end = offset + 4
            if end > len(data):
                raise ProtobufDecodeError("truncated fixed32 field")
            value = int.from_bytes(data[offset:end], "little")
            fields.append(WireField(number, wire_type, value))
            offset = end
            continue

    return fields


def looks_like_message(data: bytes) -> bool:
    if not data:
        return False

    try:
        return bool(parse_fields(data))
    except ProtobufDecodeError:
        return False


def fields_by_number(data: bytes, number: int) -> list[WireField]:
    return [field for field in parse_fields(data) if field.number == number]


def first_field(data: bytes, number: int) -> WireField | None:
    matches = fields_by_number(data, number)
    return matches[0] if matches else None


def zigzag_decode(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def extract_path(
    data: bytes,
    path: list[int],
    decode: str = "varint",
) -> Any:
    if not path:
        raise ProtobufDecodeError("field path cannot be empty")

    current = data

    for depth, field_number in enumerate(path):
        field = first_field(current, field_number)
        if field is None:
            raise ProtobufDecodeError(
                f"field {field_number} missing at depth {depth}"
            )

        is_last = depth == len(path) - 1
        if not is_last:
            if field.wire_type is not WireType.LEN or not isinstance(field.value, bytes):
                raise ProtobufDecodeError(
                    f"field {field_number} is not an embedded message"
                )
            current = field.value
            continue

        if decode == "varint":
            if field.wire_type is not WireType.VARINT or not isinstance(field.value, int):
                raise ProtobufDecodeError("target field is not a varint")
            return field.value

        if decode == "zigzag":
            if field.wire_type is not WireType.VARINT or not isinstance(field.value, int):
                raise ProtobufDecodeError("target field is not a varint")
            return zigzag_decode(field.value)

        if decode == "bool":
            if field.wire_type is not WireType.VARINT or not isinstance(field.value, int):
                raise ProtobufDecodeError("target field is not a varint")
            return bool(field.value)

        if decode == "string":
            if field.wire_type is not WireType.LEN or not isinstance(field.value, bytes):
                raise ProtobufDecodeError("target field is not length-delimited")
            return field.value.decode("utf-8")

        if decode == "bytes":
            if field.wire_type is not WireType.LEN or not isinstance(field.value, bytes):
                raise ProtobufDecodeError("target field is not length-delimited")
            return field.value

        raise ProtobufDecodeError(f"unsupported decode mode: {decode}")
