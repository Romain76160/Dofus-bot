from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


MAP_INTERACTIONS_TABLE = "map_interactions"
EXPECTED_MAP_COLUMNS = {
    "mapId",
    "worldId",
    "gfxId",
    "cellId",
    "interactionId",
}


class GameDataRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)

    def exists(self) -> bool:
        return self.db_path.exists()

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if not self.exists():
            return []

        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def tables(self) -> list[str]:
        rows = self.query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [str(row["name"]) for row in rows]

    def table_columns(self, table: str) -> list[str]:
        if table not in self.tables():
            return []

        rows = self.query(f'PRAGMA table_info("{table}")')
        return [str(row["name"]) for row in rows]

    def map_schema_valid(self) -> bool:
        columns = set(self.table_columns(MAP_INTERACTIONS_TABLE))
        return EXPECTED_MAP_COLUMNS.issubset(columns)

    def status(self) -> dict[str, Any]:
        tables = self.tables()
        return {
            "path": str(self.db_path),
            "exists": self.exists(),
            "tables": tables,
            "map_interactions_ready": self.map_schema_valid(),
            "map_interactions_columns": self.table_columns(MAP_INTERACTIONS_TABLE),
        }

    def interactions_for_map(self, map_id: int) -> list[dict[str, Any]]:
        if not self.map_schema_valid():
            return []

        return self.query(
            """
            SELECT
                mapId,
                worldId,
                gfxId,
                cellId,
                interactionId
            FROM map_interactions
            WHERE mapId = ?
            ORDER BY cellId, interactionId
            """,
            (map_id,),
        )

    def interaction_count_for_map(self, map_id: int) -> int:
        if not self.map_schema_valid():
            return 0

        rows = self.query(
            "SELECT COUNT(*) AS count FROM map_interactions WHERE mapId = ?",
            (map_id,),
        )
        return int(rows[0]["count"]) if rows else 0
