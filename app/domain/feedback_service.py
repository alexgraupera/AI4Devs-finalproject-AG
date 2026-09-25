"""Thumbs up or down on a review or an answer, kept with the request it belongs to (#51).

The golden sets are what the engineer thought of; what people ask and find wrong is what the next
golden cases should be made of. This is the smallest loop that captures it: the vote and an
optional comment, stored with the request id. Everything else about the request (the prompt
version, the model that answered, the articles it read, the cost) is already in its log events,
under the same id.

Nothing the person reviewed is stored: no listing, no question. A comment can still carry personal
data typed by hand, so it goes through the same patterns as the input guardrail, masked rather than
refused: refusing a complaint because it quotes a phone number would lose the complaint.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

import structlog

from app.domain.errors import FeedbackUnavailable
from app.domain.schemas.feedback import Feedback, RecordedFeedback
from app.foundation.guardrails.input import PII_MASK, mask_pii

log = structlog.get_logger()


class FeedbackStore(Protocol):
    async def save(self, *, request_id: UUID, kind: str, rating: str, comment: str | None) -> tuple[int, datetime]: ...


class FeedbackService:
    def __init__(self, store: FeedbackStore | None) -> None:
        self._store = store

    async def record(self, feedback: Feedback) -> RecordedFeedback:
        if self._store is None:
            # Without a database there is nowhere to keep it; saying so beats pretending.
            raise FeedbackUnavailable("no database is configured to keep feedback")
        comment = mask_pii(feedback.comment.strip()) if feedback.comment and feedback.comment.strip() else None
        id, created_at = await self._store.save(
            request_id=feedback.request_id, kind=feedback.kind.value, rating=feedback.rating.value, comment=comment
        )
        # The link a thumbs down is followed by: this event carries the request id it rates, and
        # that request's own events carry the same id. The comment's text stays in the table.
        log.info(
            "feedback.recorded",
            rated_request_id=str(feedback.request_id),
            kind=feedback.kind.value,
            rating=feedback.rating.value,
            has_comment=comment is not None,
            masked=comment is not None and PII_MASK in comment,
        )
        return RecordedFeedback(id=id, request_id=feedback.request_id, created_at=created_at)
