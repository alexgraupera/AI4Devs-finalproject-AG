"""`make benchmark-semantic-cache`: would a semantic cache serve the right review?

It embeds both listings of every pair with the configured embedding model and reports how
similar they are, grouped by what a cache hit would mean: a saved call (`reworded`) or a wrong
review (`clause-changed`, `different-flat`). It needs no database and costs a few dozen
embeddings.

    python -m benchmarks.semantic_cache.run
"""

import asyncio
import sys

from app.config import get_settings
from app.generation.rag.embeddings import PRICE_PER_MILLION_TOKENS, LiteLLMEmbeddings
from benchmarks.semantic_cache.pairs import ListingPair, PairKind, cosine, load_pairs, separation


async def measure(pairs: list[ListingPair], client: LiteLLMEmbeddings) -> list[tuple[ListingPair, float]]:
    texts = [text for pair in pairs for text in (pair.a, pair.b)]
    vectors = await client.embed(texts)
    return [(pair, cosine(vectors[2 * i], vectors[2 * i + 1])) for i, pair in enumerate(pairs)]


def render(scored: list[tuple[ListingPair, float]], *, model: str, cost_usd: float) -> str:
    lines = [f"Embedding model: {model}", "", "| Pair | Kind | A hit would be | Similarity |", "|---|---|---|---:|"]
    for pair, score in sorted(scored, key=lambda item: item[1], reverse=True):
        meaning = "a saved call" if pair.should_hit else "**a wrong review**"
        lines.append(f"| `{pair.id}` | {pair.kind} | {meaning} | {score:.4f} |")

    lines += ["", "| Kind | Min | Max |", "|---|---:|---:|"]
    for kind in PairKind:
        scores = [score for pair, score in scored if pair.kind == kind]
        if scores:
            lines.append(f"| {kind} | {min(scores):.4f} | {max(scores):.4f} |")

    result = separation(scored)
    verdict = (
        f"A threshold between {result.highest_miss:.4f} and {result.lowest_hit:.4f} separates them."
        if result.separable
        else (
            f"No threshold separates them: the lowest rewording scores {result.lowest_hit:.4f} and the "
            f"highest changed clause {result.highest_miss:.4f} (gap {result.gap:+.4f})."
        )
    )
    lines += ["", verdict, f"Cost of the run: ${cost_usd:.6f}"]
    return "\n".join(lines)


def main() -> int:
    settings = get_settings()
    client = LiteLLMEmbeddings(model=settings.embedding_model, dimensions=settings.embedding_dimensions)
    scored = asyncio.run(measure(load_pairs(), client))
    cost = client.tokens / 1_000_000 * PRICE_PER_MILLION_TOKENS.get(client.model, 0.0)
    print(render(scored, model=client.model, cost_usd=cost))
    return 0


if __name__ == "__main__":
    sys.exit(main())
