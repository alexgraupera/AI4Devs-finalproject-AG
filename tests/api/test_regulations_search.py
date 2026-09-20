from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_retriever
from app.domain.errors import CorpusUnavailable
from app.generation.rag.retriever import RetrievedChunk, Retriever
from app.main import create_app


def a_chunk(score: float = 0.82, block_id: str = "a36") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=1,
        text="Artículo 36. Fianza. Una mensualidad de renta.",
        score=score,
        law_id="BOE-A-1994-26003",
        law_title="Ley 29/1994, de Arrendamientos Urbanos",
        article_title="Artículo 36",
        block_id=block_id,
        jurisdiction="state",
        citation_url="https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
        fecha_vigencia="20190306",
    )


class FakeRetriever:
    def __init__(self, results: list[RetrievedChunk] | None = None) -> None:
        self.results = results if results is not None else [a_chunk()]
        self.calls: list[dict[str, object]] = []

    async def search(self, query: str, **kwargs: object) -> list[RetrievedChunk]:
        self.calls.append({"query": query, **kwargs})
        return self.results


@pytest.fixture
def app() -> Iterator[FastAPI]:
    application = create_app()
    yield application
    application.dependency_overrides.clear()


def client_with(app: FastAPI, retriever: FakeRetriever) -> TestClient:
    app.dependency_overrides[get_retriever] = lambda: retriever
    return TestClient(app)


def test_returns_the_retrieved_articles_with_their_scores(app: FastAPI) -> None:
    response = client_with(app, FakeRetriever()).post("/api/v1/regulations/search", json={"query": "fianza"})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "fianza"
    assert body["results"][0]["article_title"] == "Artículo 36"
    assert body["results"][0]["score"] == 0.82
    assert body["results"][0]["citation_url"].endswith("#a36")


def test_passes_the_filters_through_to_the_retriever(app: FastAPI) -> None:
    retriever = FakeRetriever()

    client_with(app, retriever).post(
        "/api/v1/regulations/search",
        json={"query": "cédula", "k": 3, "min_score": 0.5, "jurisdictions": ["catalonia"]},
    )

    assert retriever.calls[0] == {
        "query": "cédula",
        "k": 3,
        "min_score": 0.5,
        "jurisdictions": ["catalonia"],
        "law_ids": None,
    }


def test_nothing_above_the_threshold_is_an_empty_list_not_an_error(app: FastAPI) -> None:
    response = client_with(app, FakeRetriever(results=[])).post(
        "/api/v1/regulations/search", json={"query": "¿qué tiempo hará mañana?"}
    )

    assert response.status_code == 200
    assert response.json()["results"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": "fianza", "k": 0},
        {"query": "fianza", "k": 500},
        {"query": "fianza", "min_score": 1.5},
        {},
    ],
)
def test_rejects_a_nonsensical_request(app: FastAPI, payload: dict[str, object]) -> None:
    response = client_with(app, FakeRetriever()).post("/api/v1/regulations/search", json=payload)

    assert response.status_code == 422


def test_answers_503_when_the_corpus_is_not_available(app: FastAPI) -> None:
    # Without a corpus store the composition root refuses to build a retriever. The endpoint
    # turns that into an answer the caller can read, not a stack trace.
    def unavailable() -> Retriever:
        raise CorpusUnavailable("the corpus store is not configured")

    app.dependency_overrides[get_retriever] = unavailable
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/regulations/search", json={"query": "fianza"}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "corpus_unavailable"
