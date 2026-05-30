"""V1 Policies API — create and list PACT policy rules."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.policy import Policy as PolicyModel
from app.services.policy_store import encode_rules, policy_to_response, reload_runtime_policy

router = APIRouter()


class CreatePolicyRequest(BaseModel):
    policy_id: str
    name: str
    description: str = ""
    rules: list[dict] = Field(default_factory=list)
    enabled: bool = True


@router.post("")
async def create_or_update_policy(
    req: CreatePolicyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create or update a persisted policy document."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PolicyModel).where(PolicyModel.policy_id == req.policy_id)
    )
    policy = result.scalar_one_or_none()

    if policy:
        policy.name = req.name
        policy.description = req.description
        policy.rules_json = encode_rules(req.rules)
        policy.enabled = req.enabled
        policy.updated_at = now
    else:
        policy = PolicyModel(
            policy_id=req.policy_id,
            name=req.name,
            description=req.description,
            rules_json=encode_rules(req.rules),
            enabled=req.enabled,
            created_at=now,
            updated_at=now,
        )
        db.add(policy)

    await db.commit()
    await db.refresh(policy)
    await reload_runtime_policy(db)
    return policy_to_response(policy)


@router.get("")
async def list_policies(db: AsyncSession = Depends(get_db)):
    """List all active persisted policies."""
    result = await db.execute(
        select(PolicyModel)
        .where(PolicyModel.enabled.is_(True))
        .order_by(PolicyModel.id)
    )
    policies = [policy_to_response(policy) for policy in result.scalars().all()]
    return {"policies": policies, "count": len(policies)}


@router.get("/{policy_id}")
async def get_policy(policy_id: str, db: AsyncSession = Depends(get_db)):
    """Get one persisted policy document."""
    result = await db.execute(
        select(PolicyModel).where(PolicyModel.policy_id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return policy_to_response(policy)
