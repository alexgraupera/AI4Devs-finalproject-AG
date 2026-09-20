"""Assembling the retrieved articles into the context the model reads.

Retrieval returns a ranked list; a model reads a document. Turning one into the other is where
answers are quietly won or lost:

- **Numbered fragments.** The model cites by number, and the service resolves the numbers into
  citations from the retrieved set. That is what makes a citation impossible to invent.
- **Deduplicated by article.** A long article split into pieces can come back twice; showing the
  same rule twice makes the model treat it as two rules.
- **Ordered by score, and cut at the budget on a fragment boundary.** Half an article is a rule
  without its exception.
- **The jurisdiction is stated.** A state law and a Catalan one can both apply, and the model
  cannot say which is which if the context does not say it.
"""

from dataclasses import dataclass, field

from app.generation.rag.retriever import RetrievedChunk

DEFAULT_MAX_CHARS = 12_000

JURISDICTIONS = {"state": "normativa estatal", "catalonia": "normativa de Cataluña"}


@dataclass(frozen=True)
class Context:
    text: str
    chunks: list[RetrievedChunk] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.chunks

    def chunk_by_id(self, chunk_id: int) -> RetrievedChunk | None:
        return next((chunk for chunk in self.chunks if chunk.chunk_id == chunk_id), None)


def build_context(chunks: list[RetrievedChunk], *, max_chars: int = DEFAULT_MAX_CHARS) -> Context:
    kept: list[RetrievedChunk] = []
    seen: set[tuple[str, str]] = set()
    budget = 0

    for chunk in sorted(chunks, key=lambda c: c.score, reverse=True):
        article = (chunk.law_id, chunk.block_id)
        if article in seen:
            continue
        # The budget is checked before adding, so a fragment is either whole or absent. The
        # first one is kept whatever its size: an empty context is worse than an oversized one.
        if kept and budget + len(chunk.text) > max_chars:
            continue
        seen.add(article)
        kept.append(chunk)
        budget += len(chunk.text)

    return Context(text="\n\n".join(_render(chunk) for chunk in kept), chunks=kept)


def _render(chunk: RetrievedChunk) -> str:
    jurisdiction = JURISDICTIONS.get(chunk.jurisdiction, chunk.jurisdiction)
    return "\n".join(
        [
            f"[{chunk.chunk_id}] {chunk.law_title} · {chunk.article_title} ({jurisdiction})",
            chunk.text,
        ]
    )
