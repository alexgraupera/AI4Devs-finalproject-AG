from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import Settings, get_settings
from app.dependencies import get_listing_review_service, get_rate_limiter, get_retriever
from app.foundation.guardrails.rate_limit import NoRateLimit, RateLimited, RedisRateLimiter
from app.main import create_app

A_KEY = "the-configured-key"
SEARCH = "/api/v1/regulations/search"
A_QUERY = {"query": "¿cuál es la fianza?"}


class FakeRetriever:
    async def search(self, query: str, **kwargs: object) -> list[object]:
        return []


class CountingLimiter:
    def __init__(self, allowed: int = 1) -> None:
        self.allowed = allowed
        self.seen: list[str] = []

    async def check(self, identity: str) -> None:
        self.seen.append(identity)
        if self.seen.count(identity) > self.allowed:
            raise RateLimited(retry_after=42)


@pytest.fixture
def app() -> Iterator[FastAPI]:
    application = create_app()
    application.dependency_overrides[get_retriever] = FakeRetriever
    yield application
    application.dependency_overrides.clear()
    get_settings.cache_clear()


def guarded(app: FastAPI, *, key: str = A_KEY) -> TestClient:
    app.dependency_overrides[get_rate_limiter] = NoRateLimit
    app.dependency_overrides[get_settings] = lambda: Settings(api_key=key)
    return TestClient(app)


def test_a_request_without_a_key_is_rejected(app: FastAPI) -> None:
    response = guarded(app).post(SEARCH, json=A_QUERY)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_a_wrong_key_is_rejected_the_same_way_as_a_missing_one(app: FastAPI) -> None:
    # Telling an attacker which of the two it was is free information.
    missing = guarded(app).post(SEARCH, json=A_QUERY)
    wrong = guarded(app).post(SEARCH, json=A_QUERY, headers={"X-API-Key": "not-the-key"})

    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()


def test_the_configured_key_passes_through(app: FastAPI) -> None:
    response = guarded(app).post(SEARCH, json=A_QUERY, headers={"X-API-Key": A_KEY})

    assert response.status_code == 200


def test_without_a_configured_key_the_corpus_is_open(app: FastAPI) -> None:
    # Right for local development, and logged as a warning so it is never a silent state.
    response = guarded(app, key="").post(SEARCH, json=A_QUERY)

    assert response.status_code == 200


def test_the_ask_endpoint_is_guarded_too(app: FastAPI) -> None:
    response = guarded(app).post("/api/v1/regulations/ask", json={"question": "¿cuál es la fianza?"})

    assert response.status_code == 401


def test_the_limiter_counts_per_identity_and_answers_429(app: FastAPI) -> None:
    limiter = CountingLimiter(allowed=1)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    client = TestClient(app)

    first = client.post(SEARCH, json=A_QUERY)
    second = client.post(SEARCH, json=A_QUERY)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limited"


def test_a_rate_limited_answer_says_how_long_to_wait(app: FastAPI) -> None:
    app.dependency_overrides[get_rate_limiter] = lambda: CountingLimiter(allowed=0)

    response = TestClient(app).post(SEARCH, json=A_QUERY)

    assert response.headers["Retry-After"] == "42"


def test_the_message_is_written_for_the_person_reading_it(app: FastAPI) -> None:
    app.dependency_overrides[get_rate_limiter] = lambda: CountingLimiter(allowed=0)

    response = TestClient(app).post(SEARCH, json=A_QUERY)

    assert response.json()["error"]["message"] == (
        "Demasiadas consultas seguidas. Espera unos segundos y vuelve a intentarlo."
    )


def test_the_listing_review_is_guarded_too(app: FastAPI) -> None:
    # The most-called endpoint, and every call is a model call: the one an open door costs most.
    app.dependency_overrides[get_listing_review_service] = lambda: None
    response = guarded(app).post("/api/v1/listings/review", json={"text": "Piso en Chamberí"})

    assert response.status_code == 401


def test_the_old_key_name_still_configures_the_key() -> None:
    assert Settings(rag_api_key="old-name").api_key == "old-name"


def test_the_new_key_name_wins_over_the_old_one() -> None:
    assert Settings(api_key="new", rag_api_key="old").api_key == "new"


def test_health_is_not_behind_the_guards(app: FastAPI) -> None:
    # A probe that needs a secret stops working the day the secret rotates.
    app.dependency_overrides[get_rate_limiter] = lambda: CountingLimiter(allowed=0)

    assert TestClient(app).get("/health").status_code == 200


# ── The service token ───────────────────────────────────────────────────────────────────────

A_TOKEN = "the-service-token"


@pytest.fixture
def tokened() -> Iterator[TestClient]:
    application = create_app(Settings(service_token=A_TOKEN))
    application.dependency_overrides[get_retriever] = FakeRetriever
    application.dependency_overrides[get_rate_limiter] = NoRateLimit
    yield TestClient(application)
    application.dependency_overrides.clear()


def test_a_request_without_the_service_token_is_rejected(tokened: TestClient) -> None:
    response = tokened.post(SEARCH, json=A_QUERY)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_a_wrong_token_gets_the_same_answer_as_a_missing_one(tokened: TestClient) -> None:
    missing = tokened.post(SEARCH, json=A_QUERY)
    wrong = tokened.post(SEARCH, json=A_QUERY, headers={"X-Service-Token": "not-it"})

    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()


def test_the_right_token_passes_through(tokened: TestClient) -> None:
    response = tokened.post(SEARCH, json=A_QUERY, headers={"X-Service-Token": A_TOKEN})

    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/health", "/openapi.json", "/docs"])
def test_the_probes_and_the_docs_do_not_need_the_token(tokened: TestClient, path: str) -> None:
    assert tokened.get(path).status_code == 200


def test_without_a_configured_token_no_token_is_asked_for(app: FastAPI) -> None:
    # Development. Production refuses to start without one: see test_config.
    app.dependency_overrides[get_rate_limiter] = NoRateLimit

    assert TestClient(app).post(SEARCH, json=A_QUERY).status_code == 200


# ── The limiter itself ───────────────────────────────────────────────────────────────────────


class FakeRedis:
    def __init__(self, error: Exception | None = None) -> None:
        self.counters: dict[str, int] = {}
        self.expiries: list[tuple[str, int]] = []
        self.error = error

    async def incr(self, key: str) -> int:
        if self.error is not None:
            raise self.error
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expiries.append((key, seconds))


def limiter_with(client: FakeRedis, requests: int = 2) -> RedisRateLimiter:
    return RedisRateLimiter(client, requests=requests, window_seconds=60)  # type: ignore[arg-type]


async def test_allows_up_to_the_limit_then_refuses() -> None:
    limiter = limiter_with(FakeRedis(), requests=2)

    await limiter.check("caller")
    await limiter.check("caller")

    with pytest.raises(RateLimited) as limited:
        await limiter.check("caller")

    assert 0 < limited.value.retry_after <= 60


async def test_only_the_first_request_of_a_window_sets_the_expiry() -> None:
    # The window is fixed, not extended by traffic, or a busy caller would never be let back in.
    client = FakeRedis()
    limiter = limiter_with(client)

    await limiter.check("caller")
    await limiter.check("caller")

    assert len(client.expiries) == 1
    assert client.expiries[0][1] == 60


async def test_two_callers_do_not_share_an_allowance() -> None:
    limiter = limiter_with(FakeRedis(), requests=1)

    await limiter.check("first")
    await limiter.check("second")


async def test_redis_being_down_lets_the_request_through() -> None:
    # A limiter that turns an outage of an optional dependency into an outage of the product
    # has the priorities backwards.
    limiter = limiter_with(FakeRedis(error=RedisConnectionError("cache is down")))

    await limiter.check("caller")


async def test_without_redis_nothing_is_limited() -> None:
    await NoRateLimit().check("caller")
