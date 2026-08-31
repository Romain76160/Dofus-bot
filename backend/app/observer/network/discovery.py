from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from .models import Candidate


_MAP_NAMES = {
    "mapid",
    "map_id",
    "currentmapid",
    "current_map_id",
    "currentmap",
    "current_map",
}

_PLAYER_CELL_NAMES = {
    "playercell",
    "player_cell",
    "playercellid",
    "player_cell_id",
    "currentcell",
    "current_cell",
    "currentcellid",
    "current_cell_id",
    "character_cell",
    "charactercell",
    "character_cell_id",
    "charactercellid",
}

_GENERIC_CELL_NAMES = {"cell", "cellid", "cell_id"}
_PLAYER_CONTEXT = {
    "player",
    "character",
    "self",
    "me",
    "hero",
    "controlled",
    "local",
    "own",
}


def _normalized(name: str) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return snake.replace("-", "_")


def _walk(
    value: Any,
    path: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (*path, str(key))
            yield child_path, child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = (*path, str(index))
            yield child_path, child
            yield from _walk(child, child_path)


def _context_words(parts: tuple[str, ...]) -> set[str]:
    words: set[str] = set()
    for part in parts:
        if part.isdigit():
            continue
        normalized = _normalized(part)
        words.update(token for token in re.split(r"[^a-z0-9]+", normalized) if token)
    return words


def _valid_map_id(value: int) -> bool:
    return 0 < value < 2**63


def _valid_cell_id(value: int) -> bool:
    # Dofus outdoor maps use a bounded cell grid. Keep a little headroom for
    # build differences while rejecting IDs that are obviously not cells.
    return 0 <= value <= 1000


def discover_candidates(payload: dict[str, Any]) -> list[Candidate]:
    """Find likely map/cell identifiers without pinning one client build.

    Generic cell fields are deliberately conservative: they are surfaced for
    debugging but only auto-applied when nested under an explicit player-like
    context.
    """

    found: list[Candidate] = []

    for path_parts, raw_value in _walk(payload):
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            continue
        if not path_parts:
            continue

        leaf = _normalized(path_parts[-1])
        context = _context_words(path_parts[:-1])
        dotted = ".".join(path_parts)

        if leaf in _MAP_NAMES and _valid_map_id(raw_value):
            found.append(
                Candidate(
                    semantic="map_id",
                    path=dotted,
                    value=raw_value,
                    confidence=0.98,
                    reason=f"field name '{path_parts[-1]}' matches a map identifier alias",
                    auto_apply=True,
                )
            )
            continue

        if leaf in _PLAYER_CELL_NAMES and _valid_cell_id(raw_value):
            found.append(
                Candidate(
                    semantic="player_cell",
                    path=dotted,
                    value=raw_value,
                    confidence=0.98,
                    reason=f"field name '{path_parts[-1]}' explicitly describes the player cell",
                    auto_apply=True,
                )
            )
            continue

        if leaf in _GENERIC_CELL_NAMES and _valid_cell_id(raw_value):
            is_player_context = bool(context & _PLAYER_CONTEXT)
            found.append(
                Candidate(
                    semantic="player_cell" if is_player_context else "cell_id",
                    path=dotted,
                    value=raw_value,
                    confidence=0.90 if is_player_context else 0.55,
                    reason=(
                        "generic cell field is nested under player/character context"
                        if is_player_context
                        else "generic cell field; entity ownership is unknown"
                    ),
                    auto_apply=is_player_context,
                )
            )

    unique: dict[tuple[str, str, int], Candidate] = {}
    for candidate in found:
        key = (candidate.semantic, candidate.path, candidate.value)
        current = unique.get(key)
        if current is None or candidate.confidence > current.confidence:
            unique[key] = candidate

    return sorted(unique.values(), key=lambda c: (-c.confidence, c.path))
