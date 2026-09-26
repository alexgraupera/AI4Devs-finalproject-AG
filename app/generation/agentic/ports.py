"""What the agent needs from the rest of the system, declared here so it never imports it.

The `generation` siblings never import each other: `agentic/` does not know `rag/` exists. It
declares the search it needs, and the conductor adapts the concrete retriever to it. The day the
retrieval changes, the agent does not.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RegulationFragment:
    chunk_id: int
    text: str
    score: float
    law_id: str
    law_title: str
    article_title: str
    citation_url: str
    jurisdiction: str


class RegulationSearch(Protocol):
    async def search_regulations(
        self, query: str, *, jurisdictions: list[str] | None = None
    ) -> list[RegulationFragment]: ...
