"""Corpus schema: documents and chunks.

The vector column is not here. It arrives in the migration of #22, together with the embedding
model that fixes its dimensions and the index whose parameters the measurement justifies:
creating `vector(1536)` today would be guessing the model before choosing it.

Revision ID: 0001
Revises:
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        # The BOE identifier, e.g. BOE-A-1994-26003. Unique: a source is ingested once.
        sa.Column("source_id", sa.Text, nullable=False, unique=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("jurisdiction", sa.Text, nullable=False),
        sa.Column("doc_type", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        # `fecha_actualizacion` of the consolidated text: what tells us a source must be re-ingested.
        sa.Column("boe_updated_at", sa.Text, nullable=False),
        sa.Column("corpus_version", sa.Text, nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("jurisdiction IN ('state', 'catalonia')", name="documents_jurisdiction_valid"),
        sa.CheckConstraint("doc_type IN ('consolidated_law', 'resolution')", name="documents_doc_type_valid"),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        # Block id inside the consolidated text, e.g. `a36`. It is what the citation anchor uses.
        sa.Column("block_id", sa.Text, nullable=False),
        sa.Column("article_title", sa.Text, nullable=False),
        # Position of this piece inside its block: 0 unless the article had to be split.
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("char_count", sa.Integer, nullable=False),
        # fecha_vigencia, id_norma and citation_url: kept as JSON because they travel together
        # into the citation and none of them is ever filtered on its own.
        sa.Column("metadata", postgresql.JSONB, nullable=False),
        # SHA-256 of the chunk text: what makes re-ingesting a source a no-op when nothing changed.
        sa.Column("content_hash", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "block_id", "ordinal", name="chunks_block_piece_unique"),
    )
    op.create_index("chunks_document_id_idx", "chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("chunks_document_id_idx", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("documents")
    # The extension is left in place: other databases in the same cluster may be using it, and
    # dropping it would take their indexes with it.
