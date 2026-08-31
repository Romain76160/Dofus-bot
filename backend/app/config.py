from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


SourceName = Literal["network", "vision", "game_data", "manual", "system"]


def default_source_priority() -> dict[str, list[SourceName]]:
    return {
        "map_id": ["network", "manual", "vision", "game_data", "system"],
        "player_cell": ["network", "vision", "manual", "game_data", "system"],
        "in_fight": ["network", "vision", "manual", "game_data", "system"],
        "my_turn": ["network", "vision", "manual", "game_data", "system"],
        "popup_visible": ["vision", "network", "manual", "game_data", "system"],
        "interactives": ["game_data", "network", "manual", "vision", "system"],
        "network_connected": ["network", "system", "manual", "vision", "game_data"],
        "last_event": ["network", "vision", "manual", "game_data", "system"],
        "*": ["manual", "network", "vision", "game_data", "system"],
    }


class Settings(BaseSettings):
    allow_input: bool = False
    dofus_window_title: str = "Dofus"
    vision_enabled: bool = True
    vision_full_desktop_fallback: bool = False
    network_observer_enabled: bool = False
    capture_fps: int = 2
    game_data_db_path: str = "../data/maps.sqlite"
    network_profile_path: str = "config/network-profile.json"
    network_history_size: int = 100
    observation_history_size: int = 200
    conflict_history_size: int = 100
    live_capture_heartbeat_ttl_seconds: float = Field(default=7.0, gt=1.0)
    state_stale_after_seconds: float = Field(default=15.0, gt=0)
    source_priority_penalty: float = Field(default=0.15, ge=0.0, le=1.0)
    state_source_priority: dict[str, list[SourceName]] = Field(
        default_factory=default_source_priority
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
