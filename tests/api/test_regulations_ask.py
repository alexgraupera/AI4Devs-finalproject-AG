from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_regulation_qa_service
from app.domain.regulation_qa_service import NO_ANSWER, RegulationQAService
from app.domain.schemas.regulation_answer import (
    AnsweredQuestion,
    Citation,
    RegulationAnswer,
    RegulationQuestion,
)
from app.foundation.llm.usage import LLMUsage
from app.generation.rag.retriever import RetrievedChunk
from app.main import create_app

A_USAGE = LLMUsage(
    provider="anthropic",
    model="claude-haiku-4-5",
    input_tokens=2_000,
    output_tokens=200,
    latency_ms=900,
    estimated_cost_usd=Decimal("0.0030"),
)


def a_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=36,
        text="Artículo 36. Fianza.",
        score=0.72,
        law_id="BOE-A-1994-26003",
        law_title="Ley 29/1994, de Arrendamientos Urbanos",
        article_title="Artículo 36",
        block_id="a36",
        jurisdiction="state",
        citation_url="https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
        fecha_vigencia="20190306",
    )


def an_answer(*, has_answer: bool = True) -> AnsweredQuestion:
    if not has_answer:
        return AnsweredQuestion(
            answer=RegulationAnswer(answer=NO_ANSWER, citations=[], has_answer=False),
            usage=A_USAGE,
            retrieved=[],
        )
    return AnsweredQuestion(
        answer=RegulationAnswer(
            answer="La fianza es de una mensualidad.",
            citations=[Citation.of(a_chunk())],
            has_answer=True,
        ),
        usage=A_USAGE,
        retrieved=[a_chunk()],
    )


class FakeService:
    def __init__(self, answered: AnsweredQuestion) -> None:
        self.answered = answered
        self.questions: list[RegulationQuestion] = []

    async def ask(self, question: RegulationQuestion) -> AnsweredQuestion:
        self.questions.append(question)
        return self.answered


@pytest.fixture
def app() -> Iterator[FastAPI]:
    application = create_app()
    yield application
    application.dependency_overrides.clear()


def client_with(app: FastAPI, service: FakeService) -> TestClient:
    app.dependency_overrides[get_regulation_qa_service] = lambda: service
    return TestClient(app)


def test_returns_the_answer_with_its_citations(app: FastAPI) -> None:
    response = client_with(app, FakeService(an_answer())).post(
        "/api/v1/regulations/ask", json={"question": "¿Cuál es la fianza legal?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_answer"] is True
    assert body["answer"] == "La fianza es de una mensualidad."
    assert body["citations"][0]["article"] == "Artículo 36"
    assert body["citations"][0]["url"].endswith("#a36")


def test_reports_what_was_retrieved_so_an_answer_can_be_traced(app: FastAPI) -> None:
    response = client_with(app, FakeService(an_answer())).post(
        "/api/v1/regulations/ask", json={"question": "¿Cuál es la fianza legal?"}
    )

    retrieved = response.json()["retrieved"]
    assert retrieved == [{"chunk_id": 36, "article_title": "Artículo 36", "law_id": "BOE-A-1994-26003", "score": 0.72}]


def test_reports_what_the_answer_cost(app: FastAPI) -> None:
    response = client_with(app, FakeService(an_answer())).post(
        "/api/v1/regulations/ask", json={"question": "¿Cuál es la fianza legal?"}
    )

    usage = response.json()["usage"]
    assert usage["model"] == "claude-haiku-4-5"
    assert usage["input_tokens"] == 2_000


def test_a_refusal_is_a_200_with_no_citations(app: FastAPI) -> None:
    response = client_with(app, FakeService(an_answer(has_answer=False))).post(
        "/api/v1/regulations/ask", json={"question": "¿Qué tiempo hará mañana?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_answer"] is False
    assert body["citations"] == []
    assert body["answer"] == NO_ANSWER


def test_passes_the_jurisdiction_through(app: FastAPI) -> None:
    service = FakeService(an_answer())

    client_with(app, service).post(
        "/api/v1/regulations/ask",
        json={"question": "¿Qué hay que informar en Cataluña?", "jurisdictions": ["catalonia"]},
    )

    assert service.questions[0].jurisdictions == ["catalonia"]


@pytest.mark.parametrize("payload", [{"question": ""}, {}, {"question": "x" * 1_001}])
def test_rejects_a_nonsensical_question(app: FastAPI, payload: dict[str, object]) -> None:
    response = client_with(app, FakeService(an_answer())).post("/api/v1/regulations/ask", json=payload)

    assert response.status_code == 422


def test_the_service_is_the_one_wired_by_the_composition_root() -> None:
    # Guards the dependency name the overrides above rely on.
    assert get_regulation_qa_service.__annotations__["return"] is RegulationQAService
