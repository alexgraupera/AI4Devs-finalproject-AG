"""Composition root: every singleton is built here, and only here.

It lives above the layers on purpose: wiring is its job, so it is allowed to reach into any
of them. Routers and tests import it; nothing else does.
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.domain.errors import CorpusUnavailable
from app.domain.listing_review_service import ListingReviewService
from app.foundation.guardrails.input import ModerationClient
from app.foundation.guardrails.moderation import DisabledModeration, LiteLLMModeration
from app.foundation.llm.wrapper import LLMWrapper, build_router
from app.foundation.persistence.database import create_engine, session_factory
from app.generation.cag.exact import NullCache, ReviewCache, ReviewStore
from app.generation.rag.embeddings import EmbeddingClient, LiteLLMEmbeddings
from app.generation.rag.retriever import Retriever


@lru_cache
def get_llm_wrapper() -> LLMWrapper:
    settings = get_settings()
    router = build_router(
        primary_model=settings.llm_model,
        fallback_model=settings.llm_fallback_model or None,
        num_retries=settings.llm_max_retries,
    )
    return LLMWrapper(router=router, max_retries=settings.llm_max_retries)


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
def get_review_cache() -> ReviewStore:
    settings = get_settings()
    if not settings.redis_url:
        return NullCache()
    return ReviewCache.from_url(settings.redis_url, ttl_seconds=settings.cache_ttl_seconds)


@lru_cache
def get_listing_review_service() -> ListingReviewService:
    settings = get_settings()
    return ListingReviewService(
        llm=get_llm_wrapper(),
        moderation=get_moderation_client(),
        cache=get_review_cache(),
        model=settings.llm_model,
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
