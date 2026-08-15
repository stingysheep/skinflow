from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Skinflow"
    api_version: str = "0.1.0"
    environment: str = "development"
    database_path: str = "data/skinflow.db"
    csqaq_api_token: str = ""
    nameid_path: str = "data/cs2_nameids.json"
    startup_token: str = ""
    allowed_origin: str = ""
    allowed_host: str = ""
    serve_web: bool = False

    model_config = SettingsConfigDict(
        env_prefix="SKINFLOW_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
