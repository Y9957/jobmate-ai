from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "JobMate AI"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://jobmate:jobmate@localhost:5432/jobmate"

    # LLM — development runs on a local model; Claude is added for the final evaluation (docs/design.md)
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_num_ctx: int = 8192
    llm_timeout_seconds: float = 300.0

    # Pipeline
    max_match_attempts: int = 3  # first try + retries after a failed span check


@lru_cache
def get_settings() -> Settings:
    return Settings()
