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

    # Stored with every chunk, so a reindex can tell which build of the corpus it came from.
    corpus_version: str = "1"
    # Articles longer than this are split by paragraph. Measured, not guessed: see ADR 0009.
    chunk_max_chars: int = 6_000

    # Stored with every vector. Changing the model re-embeds the corpus instead of mixing two
    # vector spaces in one index; changing the dimensions also needs a migration (the column is typed).
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 100

    retrieval_top_k: int = 5
    # Below this cosine score a result is noise. Measured on 16 questions: in-domain scores land
    # between 0.598 and 0.782, out-of-domain between 0.148 and 0.403, so 0.5 sits in the middle
    # of the gap. Provisional until the benchmark of #24 measures it properly (ADR 0010).
    retrieval_min_score: float = 0.5
    # Character budget for the retrieved articles handed to the model.
    max_context_chars: int = 12_000

    # A model reads the candidates and reorders them. Measured in ADR 0013: recall@1 goes from
    # 82% to 91%, for about $0.009 and 2.4 s per question. The pool is what makes it work: with
    # 10 candidates instead of 20 the gain disappears, because the missing article is not there
    # to be rescued.
    rerank_enabled: bool = True
    rerank_pool: int = 20

    # Only read to decide whether the moderation layer can run; the providers read their own keys.
    openai_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
