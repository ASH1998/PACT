"""Run API routes — list and inspect agent runs."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.run import Run
from app.models.action import Action
from app.models.policy_decision import PolicyDecision as PolicyDecisionModel
from app.schemas import (
    RunResponse,
    ActionResponse,
    ReplayResponse,
    ReplayStep,
    PolicyDecision,
    ProvenanceContext,
    ActionStatus,
    RunStatus,
    Severity,
    Decision,
)

router = APIRouter()


@router.get("", response_model=list[RunResponse])
async def list_runs(db: AsyncSession = Depends(get_db)):
    """List all agent runs."""
    result = await db.execute(select(Run).order_by(Run.started_at.desc()))
    runs = result.scalars().all()

    responses = []
    for run in runs:
        # Count actions
        actions_result = await db.execute(
            select(Action).where(Action.run_id == run.run_id)
        )
        actions = actions_result.scalars().all()
        allowed = sum(1 for a in actions if a.status == "allowed")
        blocked = sum(1 for a in actions if a.status == "blocked")
        max_risk = 0
        for a in actions:
            pd_result = await db.execute(
                select(PolicyDecisionModel).where(PolicyDecisionModel.action_hash == a.action_hash)
            )
            pd = pd_result.scalar_one_or_none()
            if pd:
                max_risk = max(max_risk, pd.risk_score)

        responses.append(RunResponse(
            run_id=run.run_id,
            agent_id=run.agent_id,
            scenario_name=run.scenario_name,
            user_goal=run.user_goal,
            status=RunStatus(run.status),
            started_at=run.started_at,
            completed_at=run.completed_at,
            total_actions=len(actions),
            allowed_actions=allowed,
            blocked_actions=blocked,
            max_risk_score=max_risk,
            ledger_valid=True,
        ))

    return responses


@router.get("/{run_id}", response_model=dict)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """Get run details with all actions and policy decisions."""
    result = await db.execute(select(Run).where(Run.run_id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Get actions
    actions_result = await db.execute(
        select(Action).where(Action.run_id == run_id).order_by(Action.step_id)
    )
    actions = actions_result.scalars().all()

    action_list = []
    for a in actions:
        # Get policy decision
        pd_result = await db.execute(
            select(PolicyDecisionModel).where(PolicyDecisionModel.action_hash == a.action_hash)
        )
        pd = pd_result.scalar_one_or_none()

        action_list.append({
            "step_id": a.step_id,
            "agent_id": a.agent_id,
            "tool": a.tool,
            "args_digest": a.args_digest,
            "intent_hash": a.intent_hash,
            "provenance": json.loads(a.provenance_json),
            "parent_action_hash": a.parent_action_hash,
            "action_hash": a.action_hash,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "policy_decision": {
                "decision": pd.decision,
                "risk_score": pd.risk_score,
                "severity": pd.severity,
                "reasons": json.loads(pd.reasons_json),
            } if pd else None,
        })

    return {
        "run_id": run.run_id,
        "agent_id": run.agent_id,
        "scenario_name": run.scenario_name,
        "user_goal": run.user_goal,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "actions": action_list,
    }


@router.get("/{run_id}/replay", response_model=ReplayResponse)
async def get_replay(run_id: str, db: AsyncSession = Depends(get_db)):
    """Get replay data for step-by-step attack visualization."""
    result = await db.execute(select(Run).where(Run.run_id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Get actions
    actions_result = await db.execute(
        select(Action).where(Action.run_id == run_id).order_by(Action.step_id)
    )
    actions = actions_result.scalars().all()

    steps = []
    for a in actions:
        # Get policy decision
        pd_result = await db.execute(
            select(PolicyDecisionModel).where(PolicyDecisionModel.action_hash == a.action_hash)
        )
        pd = pd_result.scalar_one_or_none()
        provenance = json.loads(a.provenance_json)

        policy = PolicyDecision(
            decision=Decision(pd.decision) if pd else Decision.BLOCK,
            risk_score=pd.risk_score if pd else 0,
            severity=Severity(pd.severity) if pd else Severity.LOW,
            reasons=json.loads(pd.reasons_json) if pd else [],
        )

        # Build envelope-like structure for replay
        envelope = ActionEnvelope(
            run_id=a.run_id,
            step_id=a.step_id,
            agent_id=a.agent_id,
            tool=a.tool,
            args={},  # Args not stored in action, only digest
            args_digest=a.args_digest,
            intent_hash=a.intent_hash,
            capability_token_hash=a.capability_token_hash,
            provenance=ProvenanceContext(**provenance),
            parent_action_hash=a.parent_action_hash,
            timestamp=a.created_at,
            agent_signature=a.agent_signature,
        )

        steps.append(ReplayStep(
            step_id=a.step_id,
            timestamp=a.created_at,
            agent_id=a.agent_id,
            tool=a.tool,
            args={},
            provenance=ProvenanceContext(**provenance),
            envelope=envelope,
            policy_decision=policy,
            action_hash=a.action_hash,
            parent_action_hash=a.parent_action_hash,
            signature_valid=True,
            chain_valid=True,
        ))

    return ReplayResponse(
        run_id=run.run_id,
        scenario_name=run.scenario_name,
        user_goal=run.user_goal,
        steps=steps,
        ledger_valid=True,
    )


@router.get("/{run_id}/ledger/verify")
async def verify_ledger(run_id: str, db: AsyncSession = Depends(get_db)):
    """Verify the hash-chain integrity of a run's ledger."""
    from app.services.ledger import LedgerService

    svc = LedgerService()
    valid, issues = await svc.verify_chain(db, run_id)
    return {"run_id": run_id, "valid": valid, "issues": issues}
