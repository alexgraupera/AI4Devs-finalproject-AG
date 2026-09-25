"""Composition root: every singleton is built here, and only here.

It lives above the layers on purpose: wiring is its job, so it is allowed to reach into any
of them. Routers and tests import it; nothing else does.
"""

from functools import lru_cache

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.domain.agent_review_service import AgentReviewService, RetrieverSearch
from app.domain.errors import CorpusUnavailable
from app.domain.listing_review_service import ListingReviewService
from app.domain.regulation_qa_service import RegulationQAService
from app.foundation.guardrails.input import ModerationClient
from app.foundation.guardrails.moderation import DisabledModeration, LiteLLMModeration
from app.foundation.guardrails.rate_limit import NoRateLimit, RateLimiter, RedisRateLimiter
from app.foundation.guardrails.spend import NoSpendLimit, RedisSpendGuard, SpendGuard
from app.foundation.llm.wrapper import LLMWrapper, build_router
from app.foundation.persistence.database import create_engine, session_factory
from app.generation.cag.exact import NullCache, ReviewCache, ReviewStore
from app.generation.rag.embeddings import EmbeddingClient, LiteLLMEmbeddings
from app.generation.rag.rerank import Reranker
from app.generation.rag.retriever import Retriever


def _wrapper_for(primary_model: str, fallback_model: str) -> LLMWrapper:
    settings = get_settings()
    router = build_router(
        primary_model=primary_model,
        fallback_model=fallback_model or None,
        num_retries=settings.llm_max_retries,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    return LLMWrapper(
        router=router,
        max_retries=settings.llm_max_retries,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )


@lru_cache
def get_llm_wrapper() -> LLMWrapper:
    """The generator: writes the reviews and the answers."""
    settings = get_settings()
    return _wrapper_for(settings.llm_model, settings.llm_fallback_model)


@lru_cache
def get_judge_wrapper() -> LLMWrapper:
    """The judge: checks what the generator wrote, on the other provider (ADR 0023)."""
    settings = get_settings()
    return _wrapper_for(settings.llm_judge_model, settings.llm_judge_fallback_model)


@lru_cache
def get_rerank_wrapper() -> LLMWrapper:
    settings = get_settings()
    if not settings.llm_rerank_model:
        return get_llm_wrapper()
    return _wrapper_for(settings.llm_rerank_model, settings.llm_rerank_fallback_model)


@lru_cache
def get_moderation_client() -> ModerationClient:
    # The moderation classifier is OpenAI's and needs a key. Without one the service still runs,
    # with three of the four input layers instead of four.
    if get_settings().openai_api_key:
        return LiteLLMModeration()
    return DisabledModeration()


@lru_cache
def get_engine() -> AsyncEngine | None:
    # None is a state, not a failure: without a corpus store the review still works, and
    # /health says the database is disabled instead of pretending it is broken.
    url = get_settings().database_url
    if not url:
        return None
    return create_engine(url)


@lru_cache
def get_redis() -> Redis | None:
    # One client for the cache, the rate limiter and the spend guard: one connection pool, and
    # one place that decides that no REDIS_URL means none of the three.
    url = get_settings().redis_url
    if not url:
        return None
    return Redis.from_url(url, decode_responses=True)


@lru_cache
def get_review_cache() -> ReviewStore:
    client = get_redis()
    if client is None:
        return NullCache()
    return ReviewCache(client, ttl_seconds=get_settings().cache_ttl_seconds)


@lru_cache
def get_spend_guard() -> SpendGuard:
    client = get_redis()
    if client is None:
        return NoSpendLimit()
    return RedisSpendGuard(client, cap_usd=get_settings().daily_spend_cap_usd)


@lru_cache
def get_listing_review_service() -> ListingReviewService:
    settings = get_settings()
    return ListingReviewService(
        llm=get_llm_wrapper(),
        moderation=get_moderation_client(),
        cache=get_review_cache(),
        model=settings.llm_model,
        spend=get_spend_guard(),
    )


@lru_cache
def get_embedding_client() -> EmbeddingClient:
    settings = get_settings()
    return LiteLLMEmbeddings(
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
    )


@lru_cache
def get_retriever() -> Retriever:
    engine = get_engine()
    if engine is None:
        raise CorpusUnavailable("the corpus store is not configured")

    settings = get_settings()
    return Retriever(
        session_factory(engine),
        get_embedding_client(),
        top_k=settings.retrieval_top_k,
        min_score=settings.retrieval_min_score,
    )


@lru_cache
def get_rate_limiter() -> RateLimiter:
    client = get_redis()
    if client is None:
        return NoRateLimit()
    settings = get_settings()
    return RedisRateLimiter(
        client,
        requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )


@lru_cache
def get_reranker() -> Reranker | None:
    settings = get_settings()
    if not settings.rerank_enabled:
        return None
    return Reranker(get_rerank_wrapper(), top_n=settings.retrieval_top_k)


@lru_cache
def get_regulation_qa_service() -> RegulationQAService:
    settings = get_settings()
    return RegulationQAService(
        llm=get_llm_wrapper(),
        judge=get_judge_wrapper(),
        retriever=get_retriever(),
        moderation=get_moderation_client(),
        reranker=get_reranker(),
        check_claims=settings.grounding_enabled,
        min_confidence=settings.grounding_min_confidence,
        model=settings.llm_model,
        top_k=settings.retrieval_top_k,
        rerank_pool=settings.rerank_pool,
        max_context_chars=settings.max_context_chars,
        spend=get_spend_guard(),
    )


@lru_cache
def get_agent_review_service() -> AgentReviewService:
    settings = get_settings()
    return AgentReviewService(
        get_llm_wrapper(),
        RetrieverSearch(get_retriever(), top_k=settings.retrieval_top_k, min_score=settings.retrieval_min_score),
        get_moderation_client(),
        model=settings.llm_model,
        max_iterations=settings.agent_max_iterations,
        timeout_seconds=settings.agent_timeout_seconds,
        max_fragments=settings.agent_max_fragments,
        spend=get_spend_guard(),
        critic=get_judge_wrapper() if settings.agent_critic_enabled else None,
        critic_min_confidence=settings.agent_critic_min_confidence,
        critic_escalate_below=settings.agent_critic_escalate_below,
        max_review_attempts=settings.agent_max_review_attempts,
    )
