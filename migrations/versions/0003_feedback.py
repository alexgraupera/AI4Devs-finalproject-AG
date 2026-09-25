"""Feedback: a person's vote on a review or an answer, linked to the request that produced it (#51).

No listing, no question: the request id leads to the log events of that request, which hold the
prompt version, the model and the articles read. Personal data does not accumulate here.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        # Not unique: the same review can be rated twice (a second person, a changed mind), and
        # both votes are information.
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("rating", sa.Text, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('listing_review', 'agent_review', 'regulation_answer')", name="feedback_kind_valid"
        ),
        sa.CheckConstraint("rating IN ('up', 'down')", name="feedback_rating_valid"),
        sa.CheckConstraint("char_length(comment) <= 500", name="feedback_comment_short"),
    )
    # Read newest first: "what did people complain about this week".
    op.create_index("ix_feedback_created_at", "feedback", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_feedback_created_at", table_name="feedback")
    op.drop_table("feedback")
