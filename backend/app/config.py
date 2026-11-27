from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "JobMate AI"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://jobmate:jobmate@localhost:5432/jobmate"


@lru_cache
def get_settings() -> Settings:
    return Settings()
