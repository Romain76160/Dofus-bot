#!/usr/bin/env python3
"""Passive Windows TCP capture -> local Dofus observer backend.

This tool is intended for a private server where capture/automation is
explicitly authorized. It uses WinDivert SNIFF mode, so matching packets are
observed without being removed from the network stack.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import platform
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.observer.network.live_capture import (
    RetransmitDeduplicator,
    SegmentIdentity,
    build_capture_filter,
    infer_direction,
    payload_fingerprint,
    resolve_ipv4_addresses,
)

TOOL_VERSION = "0.7.0"


@dataclass(slots=True)
class CapturedChunk:
    direction: str
    payload: bytes


@dataclass(slots=True)
class Counters:
    packets_seen: int = 0
    payload_packets: int = 0
    chunks_forwarded: int = 0
    bytes_forwarded: int = 0
    duplicates_skipped: int = 0
    queue_drops: int = 0
    forward_errors: int = 0
    last_error: str | None = None


def is_windows_admin() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def tcp_sequence(packet: Any) -> int | None:
    tcp = getattr(packet, "tcp", None)
    if tcp is None:
        return None

    try:
        raw = bytes(tcp.raw)
    except Exception:
        return None

    if len(raw) < 8:
        return None
    return int.from_bytes(raw[4:8], "big", signed=False)


def post_json_sync(
    url: str,
    payload: Any,
    timeout: float = 5.0,
) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else None


async def post_json(
    url: str,
    payload: Any,
    timeout: float = 5.0,
) -> Any:
    return await asyncio.to_thread(post_json_sync, url, payload, timeout)


def heartbeat_payload(
    *,
    session_id: str,
    server_host: str | None,
    addresses: list[str],
    server_port: int,
    capture_filter: str,
    started_at: datetime,
    counters: Counters,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "server_host": server_host,
        "resolved_addresses": addresses,
        "server_port": server_port,
        "capture_filter": capture_filter,
        "capture_mode": "windivert_sniff",
        "platform": platform.platform(),
        "tool_version": TOOL_VERSION,
        "started_at": started_at.isoformat(),
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "packets_seen": counters.packets_seen,
        "payload_packets": counters.payload_packets,
        "chunks_forwarded": counters.chunks_forwarded,
        "bytes_forwarded": counters.bytes_forwarded,
        "duplicates_skipped": counters.duplicates_skipped,
        "queue_drops": counters.queue_drops,
        "forward_errors": counters.forward_errors,
        "last_error": counters.last_error,
    }


async def send_batch_with_retry(
    url: str,
    batch: list[CapturedChunk],
    counters: Counters,
) -> bool:
    payload = [
        {
            "direction": chunk.direction,
            "hex_data": chunk.payload.hex(),
        }
        for chunk in batch
    ]

    last_error: Exception | None = None
    for attempt, delay in enumerate((0.0, 0.15, 0.5), start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            result = await post_json(url, payload, timeout=5.0)
            if not isinstance(result, dict) or not result.get("ok"):
                raise RuntimeError(f"unexpected backend response: {result!r}")

            counters.chunks_forwarded += len(batch)
            counters.bytes_forwarded += sum(
                len(chunk.payload) for chunk in batch
            )
            counters.last_error = None
            return True
        except (
            OSError,
            TimeoutError,
            urllib.error.URLError,
            urllib.error.HTTPError,
            RuntimeError,
        ) as exc:
            last_error = exc
            counters.last_error = f"forward attempt {attempt}: {exc}"

    counters.forward_errors += 1
    counters.last_error = f"raw batch dropped: {last_error}"
    return False


async def forward_loop(
    *,
    queue: asyncio.Queue[CapturedChunk],
    replay_url: str,
    counters: Counters,
    batch_size: int,
    flush_seconds: float,
) -> None:
    while True:
        first = await queue.get()
        batch = [first]
        deadline = asyncio.get_running_loop().time() + flush_seconds

        while len(batch) < batch_size:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            batch.append(item)

        try:
            await send_batch_with_retry(replay_url, batch, counters)
        finally:
            for _ in batch:
                queue.task_done()


async def heartbeat_loop(
    *,
    heartbeat_url: str,
    session_id: str,
    server_host: str | None,
    addresses: list[str],
    server_port: int,
    capture_filter: str,
    started_at: datetime,
    counters: Counters,
    interval_seconds: float,
) -> None:
    while True:
        payload = heartbeat_payload(
            session_id=session_id,
            server_host=server_host,
            addresses=addresses,
            server_port=server_port,
            capture_filter=capture_filter,
            started_at=started_at,
            counters=counters,
        )
        try:
            await post_json(heartbeat_url, payload, timeout=3.0)
        except (
            OSError,
            TimeoutError,
            urllib.error.URLError,
            urllib.error.HTTPError,
        ) as exc:
            counters.last_error = f"heartbeat: {exc}"
        await asyncio.sleep(interval_seconds)


async def capture_loop(
    *,
    capture_filter: str,
    server_port: int,
    addresses: list[str],
    queue: asyncio.Queue[CapturedChunk],
    counters: Counters,
    dedup_window_seconds: float,
) -> None:
    try:
        import pydivert
    except ImportError as exc:
        raise RuntimeError(
            "PyDivert is not installed. Run: "
            "pip install -r requirements-live-windows.txt"
        ) from exc

    address_set = set(addresses)
    deduplicator = RetransmitDeduplicator(
        window_seconds=dedup_window_seconds
    )

    try:
        async with pydivert.WinDivert(
            capture_filter,
            flags=pydivert.Flag.SNIFF,
        ) as handle:
            print(f"[capture] SNIFF filter: {capture_filter}")
            async for packet in handle:
                counters.packets_seen += 1

                payload = bytes(packet.payload)
                if not payload:
                    continue

                direction = infer_direction(
                    src_addr=str(packet.src_addr),
                    src_port=int(packet.src_port),
                    dst_addr=str(packet.dst_addr),
                    dst_port=int(packet.dst_port),
                    server_port=server_port,
                    server_addresses=address_set,
                )
                if direction is None:
                    continue

                counters.payload_packets += 1
                identity = SegmentIdentity(
                    direction=direction,
                    src_addr=str(packet.src_addr),
                    src_port=int(packet.src_port),
                    dst_addr=str(packet.dst_addr),
                    dst_port=int(packet.dst_port),
                    sequence=tcp_sequence(packet),
                    payload_length=len(payload),
                    payload_digest=payload_fingerprint(payload),
                )
                if deduplicator.is_duplicate(identity):
                    counters.duplicates_skipped += 1
                    continue

                try:
                    queue.put_nowait(
                        CapturedChunk(
                            direction=direction,
                            payload=payload,
                        )
                    )
                except asyncio.QueueFull:
                    counters.queue_drops += 1
                    counters.last_error = (
                        "capture queue full; one TCP payload was dropped"
                    )
    except OSError as exc:
        raise RuntimeError(
            "WinDivert could not start. Run this terminal as Administrator "
            f"and verify the capture filter. Original error: {exc}"
        ) from exc


async def run(args: argparse.Namespace) -> None:
    addresses = (
        resolve_ipv4_addresses(args.server_host)
        if args.server_host
        else []
    )
    if args.server_host and not addresses:
        raise RuntimeError(
            f"no IPv4 address found for {args.server_host!r}"
        )

    capture_filter = build_capture_filter(
        args.server_port,
        addresses,
    )

    print(f"[config] server host: {args.server_host or '(port only)'}")
    print(f"[config] resolved IPv4: {', '.join(addresses) or 'none'}")
    print(f"[config] server port: {args.server_port}")
    print(f"[config] backend: {args.base_url}")
    print(f"[config] filter: {capture_filter}")

    if args.dry_run:
        return

    if platform.system() != "Windows":
        raise RuntimeError(
            "live_capture.py v0.7 targets Windows/WinDivert only"
        )
    if not is_windows_admin():
        raise RuntimeError(
            "Administrator privileges are required for WinDivert. "
            "Open PowerShell/Terminal as Administrator."
        )

    base_url = args.base_url.rstrip("/")
    replay_url = f"{base_url}/api/network/replay-batch"
    heartbeat_url = f"{base_url}/api/network/live-capture/heartbeat"

    session_id = uuid.uuid4().hex
    started_at = datetime.now(timezone.utc)
    counters = Counters()
    queue: asyncio.Queue[CapturedChunk] = asyncio.Queue(
        maxsize=args.queue_size
    )

    # Fail fast before opening the privileged capture driver.
    try:
        await post_json(
            heartbeat_url,
            heartbeat_payload(
                session_id=session_id,
                server_host=args.server_host,
                addresses=addresses,
                server_port=args.server_port,
                capture_filter=capture_filter,
                started_at=started_at,
                counters=counters,
            ),
            timeout=3.0,
        )
    except Exception as exc:
        raise RuntimeError(
            f"observer backend is not reachable at {base_url}: {exc}"
        ) from exc

    print(f"[live] session {session_id}")
    print("[live] backend reachable; starting passive capture")

    tasks = [
        asyncio.create_task(
            capture_loop(
                capture_filter=capture_filter,
                server_port=args.server_port,
                addresses=addresses,
                queue=queue,
                counters=counters,
                dedup_window_seconds=args.dedup_window_ms / 1000.0,
            ),
            name="capture",
        ),
        asyncio.create_task(
            forward_loop(
                queue=queue,
                replay_url=replay_url,
                counters=counters,
                batch_size=args.batch_size,
                flush_seconds=args.flush_ms / 1000.0,
            ),
            name="forward",
        ),
        asyncio.create_task(
            heartbeat_loop(
                heartbeat_url=heartbeat_url,
                session_id=session_id,
                server_host=args.server_host,
                addresses=addresses,
                server_port=args.server_port,
                capture_filter=capture_filter,
                started_at=started_at,
                counters=counters,
                interval_seconds=args.heartbeat_seconds,
            ),
            name="heartbeat",
        ),
    ]

    done, pending = await asyncio.wait(
        tasks,
        return_when=asyncio.FIRST_EXCEPTION,
    )

    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

    for task in done:
        exc = task.exception()
        if exc is not None:
            raise exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Passively capture authorized private-server TCP payloads and "
            "forward them to the local observer backend."
        )
    )
    parser.add_argument(
        "--server-port",
        type=int,
        required=True,
        help="TCP port used by the private game server",
    )
    parser.add_argument(
        "--server-host",
        help=(
            "Private-server hostname/IPv4. Omit to filter by port only."
        ),
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Local observer backend URL",
    )
    parser.add_argument(
        "--queue-size",
        type=int,
        default=4096,
        help="Maximum buffered TCP payload chunks",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=48,
        help="Maximum chunks sent in one ordered backend request",
    )
    parser.add_argument(
        "--flush-ms",
        type=float,
        default=35.0,
        help="Maximum batching delay in milliseconds",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=2.0,
        help="Live capture telemetry heartbeat interval",
    )
    parser.add_argument(
        "--dedup-window-ms",
        type=float,
        default=1500.0,
        help="Exact retransmission deduplication window",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve host and print the WinDivert filter without capturing",
    )
    args = parser.parse_args()

    if not 1 <= args.server_port <= 65535:
        parser.error("--server-port must be between 1 and 65535")
    if args.queue_size < 64:
        parser.error("--queue-size must be >= 64")
    if not 1 <= args.batch_size <= 500:
        parser.error("--batch-size must be between 1 and 500")
    if not 1 <= args.flush_ms <= 1000:
        parser.error("--flush-ms must be between 1 and 1000")
    if not 0.5 <= args.heartbeat_seconds <= 30:
        parser.error("--heartbeat-seconds must be between 0.5 and 30")
    if not 100 <= args.dedup_window_ms <= 10000:
        parser.error("--dedup-window-ms must be between 100 and 10000")

    return args


def main() -> int:
    try:
        asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        print("\n[live] stopped")
        return 0
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
