"""A person's verdict on a review or an answer, linked to the request that produced it (#51)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

COMMENT_MAX_CHARS = 500


class FeedbackKind(StrEnum):
    LISTING_REVIEW = "listing_review"
    AGENT_REVIEW = "agent_review"
    REGULATION_ANSWER = "regulation_answer"


class Rating(StrEnum):
    UP = "up"
    DOWN = "down"


class Feedback(BaseModel):
    """What the client sends. Never the listing or the question: the request id leads to the logs."""

    request_id: UUID
    kind: FeedbackKind
    rating: Rating
    comment: str | None = Field(default=None, max_length=COMMENT_MAX_CHARS)


@dataclass(frozen=True)
class RecordedFeedback:
    id: int
    request_id: UUID
    created_at: datetime
