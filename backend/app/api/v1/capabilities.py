"""V1 Capabilities API — issue and inspect capability tokens."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


class IssueCapabilityRequest(BaseModel):
    agent_id: str
    intent_hash: str
    capability: str
    resource: str = "default"
    max_uses: int = 5
    ttl_seconds: int = 300


@router.post("")
async def issue_capability(req: IssueCapabilityRequest, db: AsyncSession = Depends(get_db)):
    """Issue a capability token."""
    from app.core.factory import get_runtime

    runtime = get_runtime()
    result = await runtime.issue_capability(
        db=db,
        agent_id=req.agent_id,
        intent_hash=req.intent_hash,
        capability=req.capability,
        resource=req.resource,
        max_uses=req.max_uses,
        ttl_seconds=req.ttl_seconds,
    )
    return result
