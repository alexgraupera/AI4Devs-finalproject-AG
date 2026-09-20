"""`make embed`: give every chunk a vector, and skip the ones that already have a current one.

    python -m app.generation.rag.embed
    python -m app.generation.rag.embed --force   # re-embed everything, e.g. to change model

`make ingest` runs this right after writing the corpus, so one command leaves the store
queryable. The Makefile composes the two commands rather than the ingestion importing the
embeddings: `app/ingestion/` builds the corpus and knows nothing about how it is searched.
"""

import argparse
import asyncio
import sys

from app.config import get_settings
from app.foundation.persistence.database import create_engine, session_factory
from app.generation.rag.embeddings import EmbeddingReport, LiteLLMEmbeddings, embed_pending


def render(report: EmbeddingReport) -> str:
    return "\n".join(
        [
            f"Model: {report.model}",
            f"Embedded: {report.embedded} chunks",
            f"Already current: {report.already_current}",
            f"Tokens: {report.tokens:,} · estimated cost: ${report.estimated_cost_usd:.4f}",
            f"Took {report.latency_ms:,} ms",
        ]
    )


async def run(*, force: bool) -> EmbeddingReport:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured: there is no corpus to embed.")

    engine = create_engine(settings.database_url)
    try:
        return await embed_pending(
            session_factory(engine),
            LiteLLMEmbeddings(
                model=settings.embedding_model,
                dimensions=settings.embedding_dimensions,
                batch_size=settings.embedding_batch_size,
            ),
            force=force,
            batch_size=settings.embedding_batch_size,
        )
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Embed the corpus chunks that need it.")
    parser.add_argument("--force", action="store_true", help="Re-embed every chunk, whatever model it carries")
    arguments = parser.parse_args()

    print(render(asyncio.run(run(force=arguments.force))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
