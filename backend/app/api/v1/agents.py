"""V1 Agents API — register agent passports through the runtime.

Unlike the legacy /agents/register route (which signs with a standalone issuer
key), this endpoint registers via get_runtime(), so the passport is signed with
the same KeyManager passport key the gateway uses to verify it. External clients
(e.g. the Go TUI) must register here for their signed envelopes to pass.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.api.v1.demo_guard import require_insecure_demo_api

router = APIRouter()


class RegisterAgentRequest(BaseModel):
    agent_id: str
    owner: str = "external-client"
    agent_type: str = "external_agent"
    allowed_domains: list[str] = []
    risk_tier: str = "medium"
    ttl_days: int = 30


@router.post("/register")
async def register_agent(
    req: RegisterAgentRequest,
    _: None = Depends(require_insecure_demo_api),
    db: AsyncSession = Depends(get_db),
):
    """Register a demo agent passport and return its private key (shown once)."""
    existing = await db.execute(select(Agent).where(Agent.agent_id == req.agent_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Agent {req.agent_id} already registered")

    from app.core.factory import get_runtime

    runtime = get_runtime()
    result = await runtime.register_agent(
        db=db,
        agent_id=req.agent_id,
        owner=req.owner,
        agent_type=req.agent_type,
        allowed_domains=req.allowed_domains,
        risk_tier=req.risk_tier,
        ttl_days=req.ttl_days,
    )
    return {
        "agent_id": req.agent_id,
        "passport": result["passport"],
        "agent_private_key": result["agent_private_key"],
        "warning": "Store the agent_private_key securely. It will not be shown again.",
    }
