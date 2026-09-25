from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from environment variables (and `.env` when running locally)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Production refuses to start with a required secret missing (see `missing_for_production`).
    environment: Literal["development", "production"] = "development"

    api_url: str = "http://localhost:8000"

    # A model per role (ADR 0023). The generator writes reviews and answers.
    llm_model: str = "anthropic/claude-haiku-4-5"
    # Empty disables the fallback: one provider, and a failure is a failure.
    llm_fallback_model: str = "openai/gpt-5.4-mini"
    llm_max_retries: int = 2
    # The judge checks what the generator wrote (the grounding check, and the critic of #40). It
    # sits on the other provider so it does not share the generator's blind spots.
    llm_judge_model: str = "openai/gpt-5.4-mini"
    llm_judge_fallback_model: str = "anthropic/claude-haiku-4-5"
    # The reranker reads twenty articles and orders them. Empty means the generator's models.
    llm_rerank_model: str = ""
    llm_rerank_fallback_model: str = ""

    # Bounds on every call. A model call that hangs holds a request and a thread; one that runs
    # out of tokens returns half a structure. Both become named failures instead.
    llm_timeout_seconds: float = 45.0
    llm_max_tokens: int = 4_000
    # Predictable output over creative output. Models that reject the parameter get their default.
    llm_temperature: float | None = 0.0

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
    embedding_model: str = "openai/text-embedding-3-large"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 100

    retrieval_top_k: int = 5
    # Below this cosine score a result is noise. A threshold belongs to an embedding model: the
    # large model scores everything lower, and at 0.5 it dropped two answerable questions. Swept
    # over the golden set in ADR 0015: 0.40 keeps every answerable question and refuses as many
    # out-of-domain ones as 0.5 did with the small model.
    retrieval_min_score: float = 0.40
    # Character budget for the retrieved articles handed to the model.
    max_context_chars: int = 12_000

    # A model reads the candidates and reorders them. Measured in ADR 0013: recall@1 goes from
    # 82% to 91%, for about $0.009 and 2.4 s per question. The pool is what makes it work: with
    # 10 candidates instead of 20 the gain disappears, because the missing article is not there
    # to be rescued.
    rerank_enabled: bool = True
    rerank_pool: int = 20

    # A model checks that the cited articles actually support the answer's claims. Empty-ish
    # only in the sense that it can be turned off: leaving it on is the point of the layer.
    grounding_enabled: bool = True
    # Share of an answer's claims the cited articles must support. Measured, not assumed: see ADR 0014.
    grounding_min_confidence: float = 0.7

    # The agent review (ADR 0024). Every loop needs a hard exit: an impossible request must end,
    # not burn tokens until a provider rate-limits it.
    agent_max_iterations: int = 6
    agent_timeout_seconds: float = 90.0
    # Fragments per search the agent reads: its context grows with every one.
    agent_max_fragments: int = 5
    # How the agent is orchestrated (ADR 0026): a LangGraph graph whose state is checkpointed in
    # Postgres after every node, or the hand-written loop it was built from, kept as the reference.
    agent_orchestrator: Literal["graph", "loop"] = "graph"
    # Actor-critic-boss (ADR 0025): the critic judges every finding; the boss accepts at this share
    # of supported findings, sends the actor back once in between, and escalates below the floor.
    agent_critic_enabled: bool = True
    agent_critic_min_confidence: float = 0.7
    agent_critic_escalate_below: float = 0.4
    agent_max_review_attempts: int = 2

    # Business endpoints (reviews and regulations). Empty leaves them open, which is right for
    # local development and logged as a warning on every request; production refuses to start.
    api_key: str = ""
    # The name the key had while it only guarded the regulations. Still read, so an existing
    # `.env` keeps working; `api_key` wins when both are set.
    rag_api_key: str = ""
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

    # Required on every request but the probes and the docs: may you talk to this service at all.
    # It sits in front of the API key, which says which endpoints you may use (ADR 0020).
    service_token: str = ""

    # Model spend per UTC day. Reaching it stops model calls until midnight instead of alerting:
    # nobody may be watching when a loop, or someone else's script, starts spending.
    daily_spend_cap_usd: float = 2.0

    # Read to decide whether moderation can run and whether production has its providers; the
    # providers read their own keys from the environment.
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    @field_validator("database_url")
    @classmethod
    def _use_the_async_driver(cls, url: str) -> str:
        """Platforms hand out `postgres://` or `postgresql://`; the service speaks asyncpg.

        Normalised here, once, so the API, the migrations and the ingestion all read the same URL
        instead of each one learning the platform's spelling.
        """
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url.removeprefix(prefix)
        return url

    @model_validator(mode="after")
    def _adopt_the_old_key_name(self) -> "Settings":
        if not self.api_key and self.rag_api_key:
            self.api_key = self.rag_api_key
        return self

    def missing_for_production(self) -> list[str]:
        """The settings production cannot run without. Names only: a value never reaches a log.

        An empty token on both sides of a comparison is equal, so an unset service token does not
        fail, it opens the door. The same goes for the API key. That is why these are checked at
        start-up rather than trusted to be there.
        """
        if self.environment != "production":
            return []
        required = {
            "API_KEY": self.api_key,
            "SERVICE_TOKEN": self.service_token,
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "OPENAI_API_KEY": self.openai_api_key,
            "DATABASE_URL": self.database_url,
            "REDIS_URL": self.redis_url,
        }
        return [name for name, value in required.items() if not value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
