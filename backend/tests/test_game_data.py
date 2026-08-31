import sqlite3

from app.observer.game_data.repository import GameDataRepository


def test_map_interactions_repository(tmp_path):
    db_path = tmp_path / "maps.sqlite"

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE map_interactions (
                mapId INTEGER,
                worldId INTEGER,
                gfxId INTEGER,
                cellId INTEGER,
                interactionId INTEGER
            )
            """
        )
        connection.execute(
            "INSERT INTO map_interactions VALUES (?, ?, ?, ?, ?)",
            (12345, 1, 900, 214, 7),
        )

    repository = GameDataRepository(str(db_path))

    assert repository.map_schema_valid() is True
    rows = repository.interactions_for_map(12345)
    assert rows == [
        {
            "mapId": 12345,
            "worldId": 1,
            "gfxId": 900,
            "cellId": 214,
            "interactionId": 7,
        }
    ]
