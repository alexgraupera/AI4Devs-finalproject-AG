"""Vectors on the chunks, and the index the retrieval reads.

The dimensions are fixed by the embedding model, which is why this migration waited until that
model was chosen. `embedding_model` travels with every row so a change of model is visible in
the data instead of being an assumption: mixing two vector spaces in one index does not fail,
it just returns nonsense, which is the worst kind of failure.

The corpus version is not duplicated here. It lives on `documents`, one join away, and no query
filters chunks by it.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# text-embedding-3-small. Changing this is a migration, not a setting: the column is typed.
EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    op.add_column("chunks", sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=True))
    op.add_column("chunks", sa.Column("embedding_model", sa.Text, nullable=True))
    op.add_column("chunks", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))

    # HNSW over cosine distance. The corpus is 380 rows today, so any index is fast; what this
    # buys is that it stays fast when regional laws are added, without a rebuild.
    # m=16 / ef_construction=64 are pgvector's defaults: with a corpus this size, tuning them
    # would be measuring noise. Revisit with the retrieval benchmark of #24.
    op.execute("""
        CREATE INDEX chunks_embedding_hnsw_idx
        ON chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Re-embedding asks "which rows are stale for this model?" on every run, and that question
    # should not read the whole table.
    op.create_index("chunks_embedding_model_idx", "chunks", ["embedding_model"])


def downgrade() -> None:
    op.drop_index("chunks_embedding_model_idx", table_name="chunks")
    op.execute("DROP INDEX IF EXISTS chunks_embedding_hnsw_idx")
    op.drop_column("chunks", "embedded_at")
    op.drop_column("chunks", "embedding_model")
    op.drop_column("chunks", "embedding")
