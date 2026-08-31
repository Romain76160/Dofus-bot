from app.observer.network.decoder import NetworkStreamDecoder
from app.observer.network.profile import BuildProfile, MappingRule


def encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def field_varint(number: int, value: int) -> bytes:
    return encode_varint(number << 3) + encode_varint(value)


def field_len(number: int, value: bytes) -> bytes:
    return encode_varint((number << 3) | 2) + encode_varint(len(value)) + value


def make_event_frame(map_id: int) -> bytes:
    message = field_varint(1, map_id)
    any_envelope = (
        field_len(1, b"type.ankama.com/abc")
        + field_len(2, message)
    )
    payload = field_varint(1, 123) + field_len(2, any_envelope)
    return field_len(3, payload)


def test_decoder_extracts_profile_mapping():
    profile = BuildProfile(
        build="test",
        mappings={
            "abc": [
                MappingRule(
                    state_key="map_id",
                    path=[1],
                    decode="varint",
                    confidence=0.99,
                )
            ]
        },
    )
    decoder = NetworkStreamDecoder(profile=profile)

    frames = [make_event_frame(191105026) for _ in range(3)]
    stream = b"".join(encode_varint(len(frame)) + frame for frame in frames)

    packets, observations = decoder.feed("server_to_client", stream)

    assert len(packets) == 3
    assert packets[0].wire_key == "abc"
    assert packets[0].kind == "event"

    map_observations = [o for o in observations if o.key == "map_id"]
    assert len(map_observations) == 3
    assert map_observations[-1].value == 191105026
    assert map_observations[-1].source == "network"
