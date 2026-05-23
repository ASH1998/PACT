"""Run API routes — list and inspect agent runs."""

import json
from datetime import datetime, timezone

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
    ActionEnvelope,
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
    for i, a in enumerate(actions):
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

        # Load stored args from args_json
        try:
            stored_args = json.loads(a.args_json) if a.args_json else {}
        except (json.JSONDecodeError, TypeError):
            stored_args = {}

        # Use stored envelope timestamp, fallback to created_at
        envelope_ts_str = a.envelope_timestamp if a.envelope_timestamp else (a.created_at.isoformat() if a.created_at else "")
        try:
            envelope_ts = datetime.fromisoformat(envelope_ts_str)
            if envelope_ts.tzinfo is None:
                envelope_ts = envelope_ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            envelope_ts = a.created_at or datetime.now(timezone.utc)

        # Build envelope-like structure for replay
        envelope = ActionEnvelope(
            run_id=a.run_id,
            step_id=a.step_id,
            agent_id=a.agent_id,
            tool=a.tool,
            args=stored_args,
            args_digest=a.args_digest,
            intent_hash=a.intent_hash,
            capability_token_hash=a.capability_token_hash,
            provenance=ProvenanceContext(**provenance),
            parent_action_hash=a.parent_action_hash,
            timestamp=envelope_ts,
            agent_signature=a.agent_signature,
        )

        # Actually verify signature
        from app.services.envelope import EnvelopeService
        from app.models.agent import Agent

        envelope_svc = EnvelopeService()
        sig_valid = False
        agent_result = await db.execute(select(Agent).where(Agent.agent_id == a.agent_id))
        agent = agent_result.scalar_one_or_none()
        if agent:
            envelope_dict = {
                "protocol": "PACT/0.1",
                "run_id": a.run_id,
                "step_id": a.step_id,
                "agent_id": a.agent_id,
                "tool": a.tool,
                "args": stored_args,
                "args_digest": a.args_digest,
                "intent_hash": a.intent_hash,
                "capability_token_hash": a.capability_token_hash,
                "provenance": provenance,
                "parent_action_hash": a.parent_action_hash,
                "timestamp": envelope_ts.isoformat() if hasattr(envelope_ts, 'isoformat') else envelope_ts,
                "agent_signature": a.agent_signature,
            }
            sig_valid, _ = envelope_svc.verify_envelope(envelope_dict, agent.public_key)

        # Check chain linkage
        chain_valid = True
        if i == 0:
            chain_valid = a.parent_action_hash is None
        else:
            prev_action = actions[i - 1]
            chain_valid = a.parent_action_hash == prev_action.action_hash

        steps.append(ReplayStep(
            step_id=a.step_id,
            timestamp=envelope_ts,
            agent_id=a.agent_id,
            tool=a.tool,
            args=stored_args,
            provenance=ProvenanceContext(**provenance),
            envelope=envelope,
            policy_decision=policy,
            action_hash=a.action_hash,
            parent_action_hash=a.parent_action_hash,
            signature_valid=sig_valid,
            chain_valid=chain_valid,
        ))

    # Verify ledger integrity
    from app.services.ledger import LedgerService
    ledger_svc = LedgerService()
    ledger_valid, _ = await ledger_svc.verify_chain(db, run_id)

    return ReplayResponse(
        run_id=run.run_id,
        scenario_name=run.scenario_name,
        user_goal=run.user_goal,
        steps=steps,
        ledger_valid=ledger_valid,
    )


@router.get("/{run_id}/ledger/verify")
async def verify_ledger(run_id: str, db: AsyncSession = Depends(get_db)):
    """Verify the hash-chain integrity of a run's ledger."""
    from app.services.ledger import LedgerService

    svc = LedgerService()
    valid, issues = await svc.verify_chain(db, run_id)
    return {"run_id": run_id, "valid": valid, "issues": issues}
