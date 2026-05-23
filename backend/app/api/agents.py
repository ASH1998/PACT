"""Agent API routes — register and query agent passports."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.schemas import AgentRegisterRequest, AgentResponse
from app.crypto.issuer import ISSUER_PRIVATE_KEY, ISSUER_PUBLIC_KEY

router = APIRouter()

# Module-level singleton issuer keypair — reused across all requests
_ISSUER_PRIVATE = ISSUER_PRIVATE_KEY
_ISSUER_PUBLIC = ISSUER_PUBLIC_KEY


@router.post("/register", response_model=dict)
async def register_agent(
    req: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new agent and return its passport + private key."""
    from app.services.passport import PassportService

    svc = PassportService(_ISSUER_PRIVATE, _ISSUER_PUBLIC)

    # Check if agent already exists
    existing = await db.execute(select(Agent).where(Agent.agent_id == req.agent_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Agent {req.agent_id} already registered")

    result = await svc.create_passport(
        db=db,
        agent_id=req.agent_id,
        owner=req.owner,
        agent_type=req.agent_type,
        allowed_domains=req.allowed_domains,
        risk_tier=req.risk_tier.value,
        ttl_days=req.ttl_days,
    )

    return {
        "passport": result["passport"],
        "agent_private_key": result["agent_private_key"],
        "warning": "Store the agent_private_key securely. It will not be shown again.",
    }


@router.get("", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    """List all registered agents."""
    result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
    agents = result.scalars().all()

    return [
        AgentResponse(
            agent_id=a.agent_id,
            owner=a.owner,
            agent_type=a.agent_type,
            allowed_domains=__import__("json").loads(a.allowed_domains_json),
            risk_tier=a.risk_tier,
            status=a.status,
            created_at=a.created_at,
            expires_at=a.expires_at,
        )
        for a in agents
    ]


@router.get("/{agent_id}", response_model=dict)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get an agent's passport."""
    import json

    result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    return json.loads(agent.passport_json)
