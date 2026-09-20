"""The contract of a regulation answer: what goes in, and what may come out.

The model never writes a citation. It returns the **ids** of the numbered chunks it used, and
the service turns those into citations from the retrieved set. A model that writes its own URL
writes a plausible one, and a plausible URL to a wrong article is worse than no answer: the
reader checks it, sees the BOE, and trusts the rest.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.foundation.llm.usage import LLMUsage
from app.generation.rag.retriever import RetrievedChunk


class RegulationQuestion(BaseModel):
    question: str
    # Restrict the search to a jurisdiction, e.g. ["catalonia"] for a flat in Barcelona.
    jurisdictions: list[str] | None = None


class Citation(BaseModel):
    law_id: str
    law_title: str
    article: str
    url: str
    chunk_id: int

    @classmethod
    def of(cls, chunk: RetrievedChunk) -> "Citation":
        return cls(
            law_id=chunk.law_id,
            law_title=chunk.law_title,
            article=chunk.article_title,
            url=chunk.citation_url,
            chunk_id=chunk.chunk_id,
        )


class RegulationAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    has_answer: bool


class AnswerCandidate(BaseModel):
    """What the model is asked to fill, before the citations are checked.

    `has_answer` is first on purpose: the model decides whether the context covers the question
    before it starts writing, rather than writing first and justifying afterwards.
    """

    has_answer: bool = Field(description="False when the numbered context does not contain the answer to the question")
    answer: str = Field(description="The answer in Spanish, built only from the numbered context")
    cited_chunk_ids: list[int] = Field(
        default_factory=list,
        description="The numbers of the context fragments the answer is based on",
    )


@dataclass(frozen=True)
class AnsweredQuestion:
    """The answer, what it cost, and what it was built from: all three travel together."""

    answer: RegulationAnswer
    usage: LLMUsage
    retrieved: list[RetrievedChunk] = field(default_factory=list)
