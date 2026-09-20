"""Transport for the listing review. No business logic: it resolves the service and maps HTTP."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_listing_review_service
from app.domain.listing_review_service import ListingReviewService
from app.domain.schemas.listing_review import Listing, ListingReview

router = APIRouter(prefix="/api/v1/listings", tags=["listings"])


@router.post("/review", response_model=ListingReview)
async def review_listing(
    listing: Listing,
    service: Annotated[ListingReviewService, Depends(get_listing_review_service)],
) -> ListingReview:
    return await service.review(listing)
