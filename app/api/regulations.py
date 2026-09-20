"""Transport for the regulation search. No business logic: it resolves the retriever and maps HTTP.

The search ships one phase before the generated answer on purpose: retrieval quality is visible
here, with the chunks and their scores, before a model gets the chance to paper over it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.dependencies import get_retriever
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
