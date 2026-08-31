from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


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
