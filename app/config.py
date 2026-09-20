from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from environment variables (and `.env` when running locally)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_url: str = "http://localhost:8000"

    llm_model: str = "anthropic/claude-haiku-4-5"
    # Empty disables the fallback: one provider, and a failure is a failure.
    llm_fallback_model: str = "openai/gpt-5.4-mini"
    llm_max_retries: int = 2

    # Empty disables the cache: every review is computed.
    redis_url: str = ""
    cache_ttl_seconds: int = 86_400

    # Corpus store (PostgreSQL + pgvector). Empty disables it: the listing review does not
    # need a database, so the service still runs without one and says so in /health.
    database_url: str = ""

    # Only read to decide whether the moderation layer can run; the providers read their own keys.
    openai_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
