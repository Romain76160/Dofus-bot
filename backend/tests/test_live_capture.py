from app.observer.network.live_capture import (
    RetransmitDeduplicator,
    SegmentIdentity,
    build_capture_filter,
    infer_direction,
    payload_fingerprint,
)


def identity(sequence: int = 100) -> SegmentIdentity:
    payload = b"abc"
    return SegmentIdentity(
        direction="server_to_client",
        src_addr="10.0.0.2",
        src_port=5555,
        dst_addr="10.0.0.3",
        dst_port=40000,
        sequence=sequence,
        payload_length=len(payload),
        payload_digest=payload_fingerprint(payload),
    )


def test_capture_filter_is_narrow():
    result = build_capture_filter(5555, ["10.0.0.2"])

    assert "tcp.PayloadLength > 0" in result
    assert "tcp.SrcPort == 5555" in result
    assert "tcp.DstPort == 5555" in result
    assert "ip.SrcAddr == 10.0.0.2" in result
    assert "ip.DstAddr == 10.0.0.2" in result


def test_capture_filter_can_use_port_only():
    result = build_capture_filter(5555)

    assert "tcp.PayloadLength > 0" in result
    assert "5555" in result
    assert "ip.SrcAddr" not in result


def test_infer_client_to_server():
    assert (
        infer_direction(
            src_addr="10.0.0.3",
            src_port=40000,
            dst_addr="10.0.0.2",
            dst_port=5555,
            server_port=5555,
            server_addresses={"10.0.0.2"},
        )
        == "client_to_server"
    )


def test_infer_server_to_client():
    assert (
        infer_direction(
            src_addr="10.0.0.2",
            src_port=5555,
            dst_addr="10.0.0.3",
            dst_port=40000,
            server_port=5555,
            server_addresses={"10.0.0.2"},
        )
        == "server_to_client"
    )


def test_deduplicator_rejects_short_window_retransmission():
    cache = RetransmitDeduplicator(window_seconds=1.0)

    assert cache.is_duplicate(identity(), now=10.0) is False
    assert cache.is_duplicate(identity(), now=10.2) is True
    assert cache.is_duplicate(identity(), now=11.3) is False


def test_deduplicator_keeps_distinct_sequences():
    cache = RetransmitDeduplicator(window_seconds=1.0)

    assert cache.is_duplicate(identity(100), now=10.0) is False
    assert cache.is_duplicate(identity(103), now=10.1) is False
