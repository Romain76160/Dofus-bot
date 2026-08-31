from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.state.models import Observation

from .protobuf_wire import ProtobufDecodeError, extract_path


@dataclass(slots=True)
class MappingRule:
    state_key: str
    path: list[int]
    decode: str = "varint"
    confidence: float = 0.95


class BuildProfile:
    def __init__(
        self,
        build: str = "unknown",
        mappings: dict[str, list[MappingRule]] | None = None,
    ) -> None:
        self.build = build
        self.mappings = mappings or {}

    @classmethod
    def load(cls, path: str | Path) -> "BuildProfile":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        mappings: dict[str, list[MappingRule]] = {}

        for wire_key, entries in raw.get("mappings", {}).items():
            if isinstance(entries, dict):
                entries = [entries]

            mappings[wire_key] = [
                MappingRule(
                    state_key=entry["state_key"],
                    path=list(entry["path"]),
                    decode=entry.get("decode", "varint"),
                    confidence=float(entry.get("confidence", 0.95)),
                )
                for entry in entries
            ]

        return cls(build=raw.get("build", "unknown"), mappings=mappings)

    def observations_for(
        self,
        wire_key: str,
        message: bytes,
    ) -> list[Observation]:
        observations: list[Observation] = []

        for rule in self.mappings.get(wire_key, []):
            try:
                value = extract_path(message, rule.path, rule.decode)
            except (ProtobufDecodeError, UnicodeDecodeError):
                continue

            observations.append(
                Observation(
                    key=rule.state_key,
                    value=value,
                    source="network",
                    confidence=rule.confidence,
                )
            )

        return observations
