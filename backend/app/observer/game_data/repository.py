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
    """Read-only adapter for the map_interactions SQLite dataset."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def exists(self) -> bool:
        return self.db_path.is_file()

    def _connect(self) -> sqlite3.Connection:
        uri = f"file:{self.db_path.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def query(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        if not self.exists():
            return []

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def tables(self) -> list[str]:
        rows = self.query(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' ORDER BY name"
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
        ready = self.map_schema_valid()
        row_count = 0
        map_count = 0

        if ready:
            rows = self.query(
                "SELECT COUNT(*) AS rows, "
                "COUNT(DISTINCT mapId) AS maps "
                "FROM map_interactions"
            )
            if rows:
                row_count = int(rows[0]["rows"])
                map_count = int(rows[0]["maps"])

        return {
            "path": str(self.db_path),
            "exists": self.exists(),
            "tables": tables,
            "map_interactions_ready": ready,
            "map_interactions_columns": self.table_columns(
                MAP_INTERACTIONS_TABLE
            ),
            "interaction_rows": row_count,
            "map_count": map_count,
            "read_only": True,
        }

    def interactions_for_map(
        self,
        map_id: int,
    ) -> list[dict[str, Any]]:
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
            ORDER BY cellId, interactionId, gfxId
            """,
            (map_id,),
        )

    def normalized_interactions_for_map(
        self,
        map_id: int,
    ) -> list[dict[str, Any]]:
        return [
            {
                "map_id": row.get("mapId"),
                "world_id": row.get("worldId"),
                "gfx_id": row.get("gfxId"),
                "cell_id": row.get("cellId"),
                "interaction_id": row.get("interactionId"),
            }
            for row in self.interactions_for_map(map_id)
        ]

    def interaction_count_for_map(self, map_id: int) -> int:
        if not self.map_schema_valid():
            return 0

        rows = self.query(
            "SELECT COUNT(*) AS count "
            "FROM map_interactions WHERE mapId = ?",
            (map_id,),
        )
        return int(rows[0]["count"]) if rows else 0
