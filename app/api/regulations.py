"""Transport for the regulation search. No business logic: it resolves the retriever and maps HTTP.

The search ships one phase before the generated answer on purpose: retrieval quality is visible
here, with the chunks and their scores, before a model gets the chance to paper over it.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.dependencies import get_regulation_qa_service, get_retriever
from app.domain.regulation_qa_service import RegulationQAService
from app.domain.schemas.regulation_answer import AnsweredQuestion, Citation, RegulationQuestion
from app.generation.rag.retriever import RetrievedChunk, Retriever

router = APIRouter(prefix="/api/v1/regulations", tags=["regulations"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1_000)
    k: int | None = Field(default=None, ge=1, le=50)
    min_score: float | None = Field(default=None, ge=0, le=1)
    jurisdictions: list[str] | None = None
    law_ids: list[str] | None = None


class SearchResult(BaseModel):
    chunk_id: int
    text: str
    score: float
    law_id: str
    law_title: str
    article_title: str
    citation_url: str
    jurisdiction: str

    @classmethod
    def of(cls, chunk: RetrievedChunk) -> "SearchResult":
        return cls(
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            score=chunk.score,
            law_id=chunk.law_id,
            law_title=chunk.law_title,
            article_title=chunk.article_title,
            citation_url=chunk.citation_url,
            jurisdiction=chunk.jurisdiction,
        )


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


@router.post("/search", response_model=SearchResponse)
async def search_regulations(
    request: SearchRequest,
    retriever: Annotated[Retriever, Depends(get_retriever)],
) -> SearchResponse:
    chunks = await retriever.search(
        request.query,
        k=request.k,
        min_score=request.min_score,
        jurisdictions=request.jurisdictions,
        law_ids=request.law_ids,
    )
    # An empty list is an answer: nothing in the corpus passed the threshold.
    return SearchResponse(query=request.query, results=[SearchResult.of(chunk) for chunk in chunks])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1_000)
    jurisdictions: list[str] | None = None


class RetrievedSummary(BaseModel):
    """What was searched, so an answer can always be traced back to the articles behind it."""

    chunk_id: int
    article_title: str
    law_id: str
    score: float


class UsageResponse(BaseModel):
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost_usd: Decimal | None
    attempts: int


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    has_answer: bool
    usage: UsageResponse
    retrieved: list[RetrievedSummary]

    @classmethod
    def of(cls, answered: AnsweredQuestion) -> "AskResponse":
        return cls(
            answer=answered.answer.answer,
            citations=answered.answer.citations,
            has_answer=answered.answer.has_answer,
            usage=UsageResponse(**vars(answered.usage)),
            retrieved=[
                RetrievedSummary(
                    chunk_id=chunk.chunk_id,
                    article_title=chunk.article_title,
                    law_id=chunk.law_id,
                    score=chunk.score,
                )
                for chunk in answered.retrieved
            ],
        )


@router.post("/ask", response_model=AskResponse)
async def ask_regulations(
    request: AskRequest,
    service: Annotated[RegulationQAService, Depends(get_regulation_qa_service)],
) -> AskResponse:
    answered = await service.ask(RegulationQuestion(question=request.question, jurisdictions=request.jurisdictions))
    return AskResponse.of(answered)
