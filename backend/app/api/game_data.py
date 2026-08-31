from fastapi import APIRouter

from app.config import settings
from app.observer.game_data.repository import GameDataRepository

router = APIRouter(prefix="/api/game-data", tags=["game-data"])
repository = GameDataRepository(settings.game_data_db_path)


@router.get("/status")
async def game_data_status() -> dict:
    return repository.status()


@router.get("/maps/{map_id}/interactions")
async def map_interactions(map_id: int) -> dict:
    interactions = repository.interactions_for_map(map_id)
    return {
        "map_id": map_id,
        "count": len(interactions),
        "interactions": interactions,
    }
