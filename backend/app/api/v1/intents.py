"""V1 Intents API — create and list intent contracts."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.intent import Intent

router = APIRouter()


class CreateIntentRequest(BaseModel):
    user_goal: str
    created_by: str = "api"
    allowed_actions: list[str] | None = None
    forbidden_actions: list[str] | None = None


@router.post("")
async def create_intent(req: CreateIntentRequest, db: AsyncSession = Depends(get_db)):
    """Create an intent contract. Supports keyword and programmatic modes."""
    from app.core.factory import get_runtime

    runtime = get_runtime()
    result = await runtime.create_intent(
        db=db,
        user_goal=req.user_goal,
        created_by=req.created_by,
        allowed_actions=req.allowed_actions,
        forbidden_actions=req.forbidden_actions,
    )
    return result


@router.get("")
async def list_intents(db: AsyncSession = Depends(get_db)):
    """List all intent contracts."""
    result = await db.execute(select(Intent).order_by(Intent.created_at.desc()))
    intents = result.scalars().all()
    return {
        "intents": [
            {
                "intent_id": i.intent_id,
                "user_goal": i.user_goal,
                "allowed_actions": json.loads(i.allowed_actions_json),
                "forbidden_actions": json.loads(i.forbidden_actions_json),
                "risk_budget": i.risk_budget,
                "intent_hash": i.intent_hash,
                "created_by": i.created_by,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in intents
        ],
        "count": len(intents),
    }


@router.get("/{intent_id}")
async def get_intent(intent_id: str, db: AsyncSession = Depends(get_db)):
    """Get intent by ID."""
    result = await db.execute(select(Intent).where(Intent.intent_id == intent_id))
    intent = result.scalar_one_or_none()
    if not intent:
        raise HTTPException(status_code=404, detail=f"Intent {intent_id} not found")
    return {
        "intent_id": intent.intent_id,
        "user_goal": intent.user_goal,
        "allowed_actions": json.loads(intent.allowed_actions_json),
        "forbidden_actions": json.loads(intent.forbidden_actions_json),
        "risk_budget": intent.risk_budget,
        "intent_hash": intent.intent_hash,
        "created_by": intent.created_by,
    }
