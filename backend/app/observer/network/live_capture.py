from __future__ import annotations

import hashlib
import socket
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal


CaptureDirection = Literal["client_to_server", "server_to_client"]


def resolve_ipv4_addresses(host: str) -> list[str]:
    """Resolve one host to stable, unique IPv4 addresses."""
    addresses: set[str] = set()
    for family, _type, _proto, _canonname, sockaddr in socket.getaddrinfo(
        host,
        None,
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
    ):
        if family == socket.AF_INET:
            addresses.add(str(sockaddr[0]))
    return sorted(addresses)


def build_capture_filter(
    server_port: int,
    server_addresses: list[str] | None = None,
) -> str:
    """Build a narrow WinDivert network-layer filter.

    Payload-only filtering avoids SYN/ACK-only packets. When server addresses
    are known, both address and port must match. Without an address the port is
    still required, which is useful for localhost/private test servers.
    """

    if not 1 <= server_port <= 65535:
        raise ValueError("server_port must be between 1 and 65535")

    port_clause = (
        f"(tcp.SrcPort == {server_port} or tcp.DstPort == {server_port})"
    )
    clauses = ["tcp", "tcp.PayloadLength > 0", port_clause]

    addresses = sorted(set(server_addresses or []))
    if addresses:
        address_clause = " or ".join(
            f"(ip.SrcAddr == {address} or ip.DstAddr == {address})"
            for address in addresses
        )
        clauses.append(f"({address_clause})")

    return " and ".join(clauses)


def infer_direction(
    *,
    src_addr: str,
    src_port: int,
    dst_addr: str,
    dst_port: int,
    server_port: int,
    server_addresses: set[str] | None = None,
) -> CaptureDirection | None:
    """Infer logical direction using the configured private-server endpoint."""

    addresses = server_addresses or set()

    dst_is_server = dst_port == server_port and (
        not addresses or dst_addr in addresses
    )
    src_is_server = src_port == server_port and (
        not addresses or src_addr in addresses
    )

    if dst_is_server and not src_is_server:
        return "client_to_server"
    if src_is_server and not dst_is_server:
        return "server_to_client"

    # Loopback can have the same address on both ends, but the server port still
    # disambiguates the endpoint unless both ports are identical.
    if dst_port == server_port and src_port != server_port:
        return "client_to_server"
    if src_port == server_port and dst_port != server_port:
        return "server_to_client"
    return None


def payload_fingerprint(payload: bytes) -> bytes:
    return hashlib.blake2s(payload, digest_size=8).digest()


@dataclass(frozen=True, slots=True)
class SegmentIdentity:
    direction: CaptureDirection
    src_addr: str
    src_port: int
    dst_addr: str
    dst_port: int
    sequence: int | None
    payload_length: int
    payload_digest: bytes


class RetransmitDeduplicator:
    """Short-lived dedup cache for exact TCP retransmissions."""

    def __init__(
        self,
        window_seconds: float = 1.5,
        max_entries: int = 20_000,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        if max_entries <= 0:
            raise ValueError("max_entries must be > 0")
        self.window_seconds = window_seconds
        self.max_entries = max_entries
        self._seen: OrderedDict[SegmentIdentity, float] = OrderedDict()

    def _expire(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._seen:
            _key, timestamp = next(iter(self._seen.items()))
            if timestamp >= cutoff:
                break
            self._seen.popitem(last=False)

        while len(self._seen) > self.max_entries:
            self._seen.popitem(last=False)

    def is_duplicate(
        self,
        identity: SegmentIdentity,
        *,
        now: float | None = None,
    ) -> bool:
        current = time.monotonic() if now is None else now
        self._expire(current)

        previous = self._seen.get(identity)
        if previous is not None and current - previous <= self.window_seconds:
            self._seen.move_to_end(identity)
            self._seen[identity] = current
            return True

        self._seen[identity] = current
        self._seen.move_to_end(identity)
        self._expire(current)
        return False
