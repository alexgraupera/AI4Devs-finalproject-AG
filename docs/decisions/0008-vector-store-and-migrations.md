# 0008. Vector store and schema migrations

- **Status**: Accepted
- **Date**: 2026-09-20
- **Issue**: #20 (part of #2)

## Context

The RAG layer needs a place to keep the BOE corpus: the documents, the chunks they are split into, the metadata every citation is built from, and eventually the embeddings the retrieval searches over. That store has to be reproducible on a laptop, deployable with a zero infrastructure budget, and honest about its own state: the listing review of #1 works perfectly well without it, so a database that is missing or down must not take the product with it.

The options considered were a dedicated vector database (Chroma, Qdrant, Weaviate), a managed one (Pinecone), or PostgreSQL with the `pgvector` extension.

## Decision

**PostgreSQL + pgvector, not a dedicated vector database.** The corpus is small: three consolidated state laws, one regional law and the stressed-areas resolutions, roughly 115k tokens and a few thousand chunks. At that size the specialised engines win nothing measurable on retrieval, while pgvector brings two things this project actually needs: the chunk metadata lives in the same place as the vectors, so filtering by law or jurisdiction is a `WHERE` clause and not a second lookup, and the hybrid search of #25 gets PostgreSQL full-text search for free, in the same query, with no second system to keep in sync. Pinecone was discarded on the budget rule: the project runs on API credits only.

The cost is the ceiling. pgvector is not where anyone would put fifty million vectors, and an HNSW index is rebuilt rather than updated incrementally. Both are irrelevant at this corpus size and would be the reason to move.

**The schema is owned by Alembic, written by hand.** `target_metadata` stays `None` and there are no ORM models to autogenerate from: the corpus schema is small and long-lived, so it is worth reviewing as SQL in a pull request instead of diffing from whatever the models happen to say. Each migration is numbered by hand (`0001`, `0002`...) so the order is readable in the file listing.

**The database URL lives in `DATABASE_URL`, never in `alembic.ini`.** `migrations/env.py` reads the application settings, so there is one answer to "where is the database" for the service, the migrations and the tests.

**The container migrates itself.** The API starts with `alembic upgrade head && uvicorn ...`. A container that starts is a container whose schema matches the code it is running, which removes the class of bug where a deploy ships code ahead of its schema. It also means a failed migration stops the deploy, which is the intended behaviour.

**The store is optional, and says so.** An empty `DATABASE_URL` wires no engine and `GET /health` reports `"database": "disabled"`; a configured but unreachable database reports `"unavailable"` and the probe still answers 200. `check_connection` catches every failure, from a refused connection to an unresolvable host, and returns a boolean: a health probe that raises is a health probe nobody can call.

**The embedding column is not in `0001`.** Creating `vector(1536)` today would mean choosing the embedding model before measuring it. The column and its index arrive in #22 together with the model that fixes their dimensions and the numbers that justify the index parameters. The `vector` extension is created now because it is what makes the store a vector store, and `CREATE EXTENSION` is not a decision about dimensions.

**Constraints in the database, not only in the code.** `jurisdiction` and `doc_type` are restricted with `CHECK`, and `(document_id, block_id, ordinal)` is unique. That last one is the one that matters: idempotent ingestion is an acceptance criterion of #2, and it is enforced by the schema rather than trusted to the pipeline.

## Consequences

- One more service in `docker-compose.yml` and one more thing to provision when deploying (#5). Unlike the cache, its port is published: inspecting the ingested corpus with `psql` is part of working on the RAG layer.
- The default test suite stays hermetic. The database-backed tests run only when `DATABASE_URL` is **exported** (reading `.env` is deliberately not enough), so `make verify` and CI need no services. The trade-off is that those tests do not run in CI yet. Since #28 the migration tests run against their own database (`<name>_migrations`, created on the fly), because `downgrade base` drops the corpus tables and would otherwise destroy a corpus that had just been ingested.
- `metadata` as `jsonb` means its fields are not individually indexed. They are never filtered on their own, so the cost is theoretical today and a GIN index is one migration away if that changes.
- The corpus volume is local to Docker Compose. Ingestion is reproducible from the BOE API, so the volume is a cache of public data, not something to back up.
