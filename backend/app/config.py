from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    allow_input: bool = False
    dofus_window_title: str = "Dofus"
    vision_enabled: bool = True
    network_observer_enabled: bool = False
    capture_fps: int = 2
    game_data_db_path: str = "../data/maps.sqlite"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
