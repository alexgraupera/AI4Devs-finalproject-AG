"""Health probe. Thin transport layer: no business logic lives here.

It answers 200 even when the corpus store is unreachable. The listing review does not need the
database, so a store that is down is something to report, not a reason to declare the whole
service dead: the probe says which piece is missing and lets the caller decide.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dependencies import get_engine
from app.foundation.persistence.database import database_status

router = APIRouter()


@router.get("/health")
async def health(engine: Annotated[AsyncEngine | None, Depends(get_engine)]) -> dict[str, str]:
    return {"status": "ok", "database": await database_status(engine)}
