"""Cutting the corpus into the pieces the retrieval will return and the answer will cite.

**One chunk per article.** An article is what a citation points at, so a chunk that spans two
articles cannot be cited precisely and a chunk that is half an article cites a rule the reader
cannot check. Only the few articles above `max_chars` are split, and always on a paragraph
boundary: measured over the real corpus, the longest paragraph is 1,358 characters, so the
splitter never has to cut mid-sentence.

A continuation piece is prefixed with the article title. Without it, a chunk that starts at
"2. Durante los cinco primeros años..." is a rule with no subject, and that is what the model
would have to answer from.

`fixed_size_chunks` exists only to be measured against this: see the decision record.
"""

import hashlib
from dataclasses import dataclass

from app.ingestion.boe.consolidated import ParsedArticle
from app.ingestion.boe.resolutions import StressedAreaDeclaration

DEFAULT_MAX_CHARS = 6_000

CONTINUATION = "{title} (continuación)"
DECLARATION_TITLE = "Zona de mercado residencial tensionado"


@dataclass(frozen=True)
class Chunk:
    block_id: str
    article_title: str
    # Position of this piece inside its block: 0 unless the article had to be split.
    ordinal: int
    text: str
    char_count: int
    metadata: dict[str, str]
    content_hash: str


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_article(article: ParsedArticle, *, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    metadata = {
        "fecha_vigencia": article.fecha_vigencia,
        "id_norma": article.id_norma,
        "citation_url": article.citation_url,
    }
    pieces = _split_by_paragraph(article.text, max_chars)
    if len(pieces) == 1:
        return [_chunk(article.block_id, article.article_title, 0, pieces[0], metadata)]

    return [
        _chunk(
            article.block_id,
            article.article_title,
            ordinal,
            piece if ordinal == 0 else f"{CONTINUATION.format(title=article.article_title)}\n{piece}",
            metadata,
        )
        for ordinal, piece in enumerate(pieces)
    ]


def chunk_declaration(declaration: StressedAreaDeclaration) -> Chunk:
    return _chunk(
        declaration.block_id,
        DECLARATION_TITLE,
        0,
        declaration.text,
        {
            "fecha_vigencia": declaration.published_on,
            "id_norma": declaration.source_id,
            "citation_url": declaration.citation_url,
        },
    )


def fixed_size_chunks(text: str, *, size: int, overlap: int) -> list[str]:
    """The baseline the article chunking is measured against. Never used by the pipeline."""
    if size <= 0 or overlap >= size:
        raise ValueError("size must be positive and larger than the overlap")
    step = size - overlap
    return [text[start : start + size] for start in range(0, max(len(text), 1), step)]


def _chunk(block_id: str, article_title: str, ordinal: int, text: str, metadata: dict[str, str]) -> Chunk:
    return Chunk(
        block_id=block_id,
        article_title=article_title,
        ordinal=ordinal,
        text=text,
        char_count=len(text),
        metadata=metadata,
        content_hash=content_hash(text),
    )


def _split_by_paragraph(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    current: list[str] = []
    length = 0
    for paragraph in text.split("\n"):
        # A single paragraph longer than the budget has nowhere to break: it goes out whole
        # rather than being cut mid-sentence. No paragraph in the corpus reaches this today.
        if length and length + len(paragraph) + 1 > max_chars:
            pieces.append("\n".join(current))
            current, length = [], 0
        current.append(paragraph)
        length += len(paragraph) + 1

    if current:
        pieces.append("\n".join(current))
    return pieces
