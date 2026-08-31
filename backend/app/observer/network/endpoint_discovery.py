from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from typing import Iterable


@dataclass(frozen=True, slots=True)
class EndpointCandidate:
    host: str
    port: int
    pid: int
    process_name: str
    status: str = "ESTABLISHED"

    @property
    def is_loopback(self) -> bool:
        try:
            return ip_address(self.host).is_loopback
        except ValueError:
            return False

    @property
    def is_private(self) -> bool:
        try:
            return ip_address(self.host).is_private
        except ValueError:
            return False


def score_candidate(candidate: EndpointCandidate) -> tuple[int, int, int]:
    """Rank likely game endpoints without hard-coding any public service.

    Custom/private-server ports get preference over common web ports. Loopback
    and RFC1918/private addresses are also preferred because they are common in
    local/private-server development.
    """

    common_web_ports = {80, 443, 8080, 8443}
    score = 0

    if candidate.status.upper() == "ESTABLISHED":
        score += 100

    if candidate.port not in common_web_ports:
        score += 40

    if candidate.is_loopback:
        score += 35
    elif candidate.is_private:
        score += 20

    # Tie-break deterministically by lower port then PID.
    return (score, -candidate.port, -candidate.pid)


def select_endpoint(
    candidates: Iterable[EndpointCandidate],
) -> tuple[EndpointCandidate | None, list[EndpointCandidate], bool]:
    """Return (selected, ranked, ambiguous).

    The best endpoint is auto-selected only when it clearly outranks the second
    candidate. Otherwise the caller should show the candidate list and ask for
    an explicit index.
    """

    unique: dict[tuple[str, int, int], EndpointCandidate] = {}
    for candidate in candidates:
        unique[(candidate.host, candidate.port, candidate.pid)] = candidate

    ranked = sorted(
        unique.values(),
        key=score_candidate,
        reverse=True,
    )
    if not ranked:
        return None, [], False

    if len(ranked) == 1:
        return ranked[0], ranked, False

    best_score = score_candidate(ranked[0])[0]
    second_score = score_candidate(ranked[1])[0]

    if best_score - second_score >= 20:
        return ranked[0], ranked, False

    return None, ranked, True


def discover_process_tcp_endpoints(
    process_names: list[str],
) -> list[EndpointCandidate]:
    """Discover established remote TCP endpoints for matching local processes."""

    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError(
            "psutil is required for endpoint auto-discovery. "
            "Install requirements-live-windows.txt."
        ) from exc

    wanted = {name.casefold() for name in process_names}
    pid_to_name: dict[int, str] = {}

    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = str(process.info.get("name") or "")
            if name.casefold() in wanted:
                pid_to_name[int(process.info["pid"])] = name
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not pid_to_name:
        return []

    candidates: list[EndpointCandidate] = []
    for connection in psutil.net_connections(kind="tcp"):
        if connection.pid not in pid_to_name:
            continue
        if not connection.raddr:
            continue
        status = str(connection.status or "")
        if status.upper() != "ESTABLISHED":
            continue

        candidates.append(
            EndpointCandidate(
                host=str(connection.raddr.ip),
                port=int(connection.raddr.port),
                pid=int(connection.pid),
                process_name=pid_to_name[int(connection.pid)],
                status=status,
            )
        )

    return candidates
