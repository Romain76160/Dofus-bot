import asyncio
from datetime import datetime, timezone

from app.observer.network.models import LiveCaptureHeartbeat
from app.observer.network.service import NetworkEventService


def test_live_capture_heartbeat_is_reported_active():
    async def run():
        service = NetworkEventService(history_size=2)
        heartbeat = LiveCaptureHeartbeat(
            session_id="abc123",
            server_host="private.example",
            resolved_addresses=["10.0.0.2"],
            server_port=5555,
            capture_filter=(
                "tcp and tcp.PayloadLength > 0 and "
                "(tcp.SrcPort == 5555 or tcp.DstPort == 5555)"
            ),
            platform="Windows-11",
            tool_version="0.7.0",
            started_at=datetime.now(timezone.utc),
            packets_seen=100,
            payload_packets=80,
            chunks_forwarded=75,
            bytes_forwarded=12345,
            duplicates_skipped=3,
            queue_drops=1,
            forward_errors=2,
        )

        reported = await service.live_capture_heartbeat(heartbeat)
        status = await service.live_capture_status()

        assert reported.active is True
        assert status.active is True
        assert status.session_id == "abc123"
        assert status.server_port == 5555
        assert status.packets_seen == 100
        assert status.chunks_forwarded == 75
        assert status.duplicates_skipped == 3
        assert status.queue_drops == 1
        assert status.forward_errors == 2
        assert status.heartbeat_age_seconds is not None

    asyncio.run(run())


def test_live_capture_status_is_empty_before_heartbeat():
    async def run():
        service = NetworkEventService(history_size=2)
        status = await service.live_capture_status()

        assert status.active is False
        assert status.session_id is None
        assert status.heartbeat_age_seconds is None

    asyncio.run(run())
