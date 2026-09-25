"""`POST /api/v1/feedback`: a thumbs up or down on a review or an answer, with its request id (#51)."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.api.security import enforce_rate_limit
from app.dependencies import get_feedback_service
from app.domain.feedback_service import FeedbackService
from app.domain.schemas.feedback import Feedback

# Behind the same key and rate limit as the reviews: an open vote box is a box anyone can stuff.
router = APIRouter(prefix="/api/v1", tags=["feedback"], dependencies=[Depends(enforce_rate_limit)])


class FeedbackResponse(BaseModel):
    id: int
    request_id: UUID
    created_at: datetime


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def record_feedback(
    feedback: Feedback,
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
) -> FeedbackResponse:
    recorded = await service.record(feedback)
    return FeedbackResponse(id=recorded.id, request_id=recorded.request_id, created_at=recorded.created_at)
