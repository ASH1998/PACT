"""Intent API routes — create and query intent contracts."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import IntentCreateRequest, IntentResponse
from app.services.intent import IntentService

router = APIRouter()


@router.post("/create", response_model=IntentResponse)
async def create_intent(
    req: IntentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create an intent contract from a user goal."""
    svc = IntentService()
    result = await svc.create_intent(db, req.user_goal, created_by=req.created_by)
    return IntentResponse(**result)


@router.get("/{intent_id}", response_model=IntentResponse)
async def get_intent(intent_id: str, db: AsyncSession = Depends(get_db)):
    """Get an intent contract by ID."""
    svc = IntentService()
    result = await svc.get_intent(db, intent_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Intent {intent_id} not found")
    return IntentResponse(**result)
