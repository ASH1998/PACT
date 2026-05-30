"""V1 Runs API — CRUD and verification for agent runs."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.run import Run
from app.models.action import Action
from app.models.policy_decision import PolicyDecision as PolicyDecisionModel

router = APIRouter()


class CreateRunRequest(BaseModel):
    agent_id: str = "v1_user"
    scenario_name: str | None = None
    user_goal: str | None = None


@router.post("")
async def create_run(req: CreateRunRequest, db: AsyncSession = Depends(get_db)):
    """Create a new run."""
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    run = Run(
        run_id=run_id,
        agent_id=req.agent_id,
        scenario_name=req.scenario_name,
        user_goal=req.user_goal,
        status="running",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    return {
        "run_id": run.run_id,
        "agent_id": run.agent_id,
        "scenario_name": run.scenario_name,
        "user_goal": run.user_goal,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
    }


@router.get("/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """Get run details."""
    result = await db.execute(select(Run).where(Run.run_id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Count actions
    actions_result = await db.execute(
        select(Action).where(Action.run_id == run_id)
    )
    actions = actions_result.scalars().all()
    allowed = sum(1 for a in actions if a.status == "allowed")
    blocked = sum(1 for a in actions if a.status == "blocked")

    return {
        "run_id": run.run_id,
        "agent_id": run.agent_id,
        "scenario_name": run.scenario_name,
        "user_goal": run.user_goal,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "total_actions": len(actions),
        "allowed_actions": allowed,
        "blocked_actions": blocked,
    }


class ModelEventRequest(BaseModel):
    provider: str
    model: str
    request_json: str = "{}"
    response_json: str = "{}"
    tool_calls: list | None = None
    token_usage: dict | None = None


@router.post("/{run_id}/model-events")
async def record_model_event(
    run_id: str, req: ModelEventRequest, db: AsyncSession = Depends(get_db)
):
    """Record a model interaction event for a run (shown in the dashboard)."""
    result = await db.execute(select(Run).where(Run.run_id == run_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    from app.core.factory import get_runtime

    runtime = get_runtime()
    return await runtime.record_model_event(
        db=db,
        run_id=run_id,
        provider=req.provider,
        model=req.model,
        request_json=req.request_json,
        response_json=req.response_json,
        tool_calls=req.tool_calls,
        token_usage=req.token_usage,
    )


@router.post("/{run_id}/complete")
async def complete_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """Mark a run as completed."""
    from datetime import datetime, timezone

    result = await db.execute(select(Run).where(Run.run_id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"run_id": run_id, "status": run.status}


@router.get("/{run_id}/replay")
async def get_replay(run_id: str, db: AsyncSession = Depends(get_db)):
    """Get replay data for a run."""
    result = await db.execute(select(Run).where(Run.run_id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    actions_result = await db.execute(
        select(Action).where(Action.run_id == run_id).order_by(Action.step_id)
    )
    actions = actions_result.scalars().all()

    steps = []
    for a in actions:
        pd_result = await db.execute(
            select(PolicyDecisionModel).where(PolicyDecisionModel.action_hash == a.action_hash)
        )
        pd = pd_result.scalar_one_or_none()

        steps.append({
            "step_id": a.step_id,
            "tool": a.tool,
            "status": a.status,
            "action_hash": a.action_hash,
            "policy_decision": {
                "decision": pd.decision,
                "risk_score": pd.risk_score,
                "severity": pd.severity,
                "reasons": json.loads(pd.reasons_json),
            } if pd else None,
        })

    return {"run_id": run_id, "steps": steps}


@router.get("/{run_id}/ledger/verify")
async def verify_ledger(run_id: str, db: AsyncSession = Depends(get_db)):
    """Verify the ledger hash chain for a run."""
    from app.core.factory import get_runtime

    runtime = get_runtime()
    valid, issues = await runtime.ledger_service.verify_chain(db, run_id)
    return {"run_id": run_id, "valid": valid, "issues": issues}
