from app.generation.rag.context import build_context
from app.generation.rag.retriever import RetrievedChunk


def a_chunk(
    chunk_id: int,
    *,
    score: float = 0.7,
    block_id: str = "a36",
    text: str = "Fianza de una mensualidad",
    law_id: str = "BOE-A-1994-26003",
    jurisdiction: str = "state",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        score=score,
        law_id=law_id,
        law_title="Ley 29/1994",
        article_title=f"Artículo {block_id.lstrip('a')}",
        block_id=block_id,
        jurisdiction=jurisdiction,
        citation_url=f"https://www.boe.es/buscar/act.php?id={law_id}#{block_id}",
        fecha_vigencia="20190306",
    )


def test_numbers_every_fragment_so_the_model_can_cite_it() -> None:
    context = build_context([a_chunk(7), a_chunk(9, block_id="a20", score=0.6)])

    assert "[7]" in context.text
    assert "[9]" in context.text


def test_keeps_the_order_it_is_given() -> None:
    # The caller ranked them: the retriever by similarity, or the reranker after reading them.
    # Sorting by score here would silently undo the reranker's work, which is how that bug was
    # introduced in the first place.
    context = build_context([a_chunk(1, score=0.4), a_chunk(2, block_id="a20", score=0.9)])

    assert context.text.index("[1]") < context.text.index("[2]")
    assert [chunk.chunk_id for chunk in context.chunks] == [1, 2]


def test_deduplicates_the_pieces_of_the_same_article() -> None:
    # A long article is stored as several chunks; showing it twice makes it look like two rules.
    context = build_context([a_chunk(1, block_id="a36"), a_chunk(2, block_id="a36", score=0.5)])

    assert [chunk.chunk_id for chunk in context.chunks] == [1]


def test_the_same_block_id_in_two_different_laws_is_not_a_duplicate() -> None:
    # Block ids are only unique within a law: `a36` exists in the LAU and in the Catalan law.
    context = build_context([a_chunk(1), a_chunk(2, law_id="BOE-A-2008-3657", score=0.6)])

    assert [chunk.chunk_id for chunk in context.chunks] == [1, 2]


def test_cuts_at_the_budget_on_a_fragment_boundary() -> None:
    chunks = [a_chunk(i, block_id=f"a{i}", text="x" * 400) for i in range(5)]

    context = build_context(chunks, max_chars=1_000)

    assert [chunk.chunk_id for chunk in context.chunks] == [0, 1]
    assert all(len(chunk.text) == 400 for chunk in context.chunks)


def test_keeps_the_best_fragment_even_when_it_alone_exceeds_the_budget() -> None:
    # An empty context is worse than an oversized one: it guarantees a refusal.
    context = build_context([a_chunk(1, text="x" * 5_000)], max_chars=1_000)

    assert [chunk.chunk_id for chunk in context.chunks] == [1]


def test_states_the_jurisdiction_of_every_fragment() -> None:
    context = build_context([a_chunk(1), a_chunk(2, law_id="BOE-A-2008-3657", jurisdiction="catalonia", score=0.6)])

    assert "normativa estatal" in context.text
    assert "normativa de Cataluña" in context.text


def test_an_empty_retrieval_produces_an_empty_context() -> None:
    context = build_context([])

    assert context.is_empty
    assert context.text == ""


def test_finds_a_fragment_by_the_id_the_model_cites() -> None:
    context = build_context([a_chunk(42)])

    assert context.chunk_by_id(42) is not None
    assert context.chunk_by_id(99) is None
