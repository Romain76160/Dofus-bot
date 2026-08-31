from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
