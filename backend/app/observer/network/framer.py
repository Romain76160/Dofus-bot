from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .protobuf_wire import ProtobufDecodeError, looks_like_message, read_varint


class HeaderKind(str, Enum):
    VARINT = "varint"
    U16_BE = "u16be"
    U32_BE = "u32be"


@dataclass(frozen=True, slots=True)
class Layout:
    header: HeaderKind
    includes_self: bool = False
    lead_skip: int = 0


CANDIDATES = (
    Layout(HeaderKind.VARINT, False, 0),
    Layout(HeaderKind.VARINT, False, 1),
    Layout(HeaderKind.U16_BE, False, 0),
    Layout(HeaderKind.U16_BE, False, 1),
    Layout(HeaderKind.U16_BE, True, 0),
    Layout(HeaderKind.U32_BE, False, 0),
    Layout(HeaderKind.U32_BE, False, 1),
)


class StreamFramer:
    def __init__(self, max_frame_size: int = 8 * 1024 * 1024) -> None:
        self._buffer = bytearray()
        self.layout: Layout | None = None
        self.max_frame_size = max_frame_size

    def feed(self, chunk: bytes) -> list[bytes]:
        self._buffer.extend(chunk)

        if self.layout is None:
            self.layout = self._detect_layout()

        if self.layout is None:
            return []

        frames: list[bytes] = []
        while True:
            parsed = self._read_one(bytes(self._buffer), self.layout)
            if parsed is None:
                break

            consumed, body = parsed
            frames.append(body)
            del self._buffer[:consumed]

        return frames

    def _read_header(self, data: bytes, kind: HeaderKind) -> tuple[int, int] | None:
        if kind is HeaderKind.VARINT:
            try:
                value, offset = read_varint(data, 0)
                return offset, value
            except ProtobufDecodeError:
                return None

        if kind is HeaderKind.U16_BE:
            if len(data) < 2:
                return None
            return 2, int.from_bytes(data[:2], "big")

        if len(data) < 4:
            return None
        return 4, int.from_bytes(data[:4], "big")

    def _read_one(self, data: bytes, layout: Layout) -> tuple[int, bytes] | None:
        header = self._read_header(data, layout.header)
        if header is None:
            return None

        header_len, raw_length = header
        if raw_length <= 0 or raw_length > self.max_frame_size:
            return None

        payload_length = raw_length - header_len if layout.includes_self else raw_length
        if payload_length <= 0:
            return None

        total = header_len + payload_length
        if len(data) < total:
            return None

        body = data[header_len:total]
        if layout.lead_skip:
            if len(body) <= layout.lead_skip:
                return None
            body = body[layout.lead_skip:]

        return total, body

    def _detect_layout(self) -> Layout | None:
        data = bytes(self._buffer)
        best: tuple[int, Layout] | None = None

        for candidate in CANDIDATES:
            offset = 0
            parsed_count = 0

            for _ in range(8):
                item = self._read_one(data[offset:], candidate)
                if item is None:
                    break

                consumed, body = item
                if len(body) < 2 or not looks_like_message(body):
                    break

                parsed_count += 1
                offset += consumed

            if parsed_count >= 3 and (
                best is None or parsed_count > best[0]
            ):
                best = (parsed_count, candidate)

        return best[1] if best else None
