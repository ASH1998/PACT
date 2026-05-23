"""Dashboard API routes — aggregate metrics for the SOC dashboard."""

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.run import Run
from app.models.action import Action
from app.models.policy_decision import PolicyDecision as PolicyDecisionModel
from app.models.agent import Agent
from app.schemas import DashboardOverview, AgentTrustScore

router = APIRouter()


@router.get("/overview", response_model=DashboardOverview)
async def get_overview(db: AsyncSession = Depends(get_db)):
    """Get aggregate dashboard metrics."""
    # Total runs
    runs_result = await db.execute(select(func.count(Run.id)))
    total_runs = runs_result.scalar() or 0

    # Total actions
    actions_result = await db.execute(select(func.count(Action.id)))
    total_actions = actions_result.scalar() or 0

    # Allowed/blocked
    allowed_result = await db.execute(
        select(func.count(Action.id)).where(Action.status == "allowed")
    )
    allowed_actions = allowed_result.scalar() or 0

    blocked_result = await db.execute(
        select(func.count(Action.id)).where(Action.status == "blocked")
    )
    blocked_actions = blocked_result.scalar() or 0

    # Critical events
    critical_result = await db.execute(
        select(func.count(PolicyDecisionModel.id)).where(PolicyDecisionModel.severity == "critical")
    )
    critical_events = critical_result.scalar() or 0

    # Top attacked tools (tools with most blocks)
    top_tools_result = await db.execute(
        select(Action.tool, func.count(Action.id).label("count"))
        .where(Action.status == "blocked")
        .group_by(Action.tool)
        .order_by(func.count(Action.id).desc())
        .limit(5)
    )
    top_attacked_tools = [{"tool": row[0], "count": row[1]} for row in top_tools_result.all()]

    # Top provenance sources
    # This is a simplified version; real implementation would parse provenance_json
    top_prov_result = await db.execute(
        select(Action.tool, func.count(Action.id).label("count"))
        .group_by(Action.tool)
        .order_by(func.count(Action.id).desc())
        .limit(5)
    )
    top_provenance_sources = [{"source": row[0], "count": row[1]} for row in top_prov_result.all()]

    # Risk timeline (simplified: recent decisions)
    timeline_result = await db.execute(
        select(PolicyDecisionModel)
        .order_by(PolicyDecisionModel.created_at.desc())
        .limit(20)
    )
    risk_timeline = [
        {
            "timestamp": pd.created_at.isoformat() if pd.created_at else None,
            "risk_score": pd.risk_score,
            "severity": pd.severity,
            "decision": pd.decision,
        }
        for pd in timeline_result.scalars().all()
    ]

    return DashboardOverview(
        total_runs=total_runs,
        total_actions=total_actions,
        allowed_actions=allowed_actions,
        blocked_actions=blocked_actions,
        critical_events=critical_events,
        top_attacked_tools=top_attacked_tools,
        top_provenance_sources=top_provenance_sources,
        risk_timeline=risk_timeline,
    )


@router.get("/agents", response_model=list[AgentTrustScore])
async def get_agent_trust_scores(db: AsyncSession = Depends(get_db)):
    """Get agent trust scores."""
    agents_result = await db.execute(select(Agent))
    agents = agents_result.scalars().all()

    scores = []
    for agent in agents:
        # Count blocked actions for this agent
        blocked_result = await db.execute(
            select(func.count(Action.id))
            .where(Action.agent_id == agent.agent_id)
            .where(Action.status == "blocked")
        )
        blocked = blocked_result.scalar() or 0

        # Count total runs
        runs_result = await db.execute(
            select(func.count(Run.id))
            .where(Run.agent_id == agent.agent_id)
        )
        total_runs = runs_result.scalar() or 0

        # Simple trust score: 100 - (blocked * 10), min 0
        trust_score = max(0, 100 - (blocked * 10))

        scores.append(AgentTrustScore(
            agent_id=agent.agent_id,
            owner=agent.owner,
            risk_tier=agent.risk_tier,
            trust_score=trust_score,
            total_runs=total_runs,
            blocked_actions=blocked,
            status=agent.status,
        ))

    return scores


@router.get("/risk-timeline")
async def get_risk_timeline(db: AsyncSession = Depends(get_db)):
    """Get risk timeline data for charts."""
    result = await db.execute(
        select(PolicyDecisionModel)
        .order_by(PolicyDecisionModel.created_at.desc())
        .limit(50)
    )
    decisions = result.scalars().all()

    return [
        {
            "timestamp": pd.created_at.isoformat() if pd.created_at else None,
            "risk_score": pd.risk_score,
            "severity": pd.severity,
            "decision": pd.decision,
            "run_id": pd.run_id,
        }
        for pd in decisions
    ]


@router.get("/blocked-actions")
async def get_blocked_actions(db: AsyncSession = Depends(get_db)):
    """Get recent blocked actions."""
    result = await db.execute(
        select(Action, PolicyDecisionModel)
        .join(PolicyDecisionModel, PolicyDecisionModel.action_hash == Action.action_hash)
        .where(Action.status == "blocked")
        .order_by(Action.created_at.desc())
        .limit(20)
    )
    rows = result.all()

    return [
        {
            "run_id": action.run_id,
            "step_id": action.step_id,
            "agent_id": action.agent_id,
            "tool": action.tool,
            "risk_score": pd.risk_score,
            "severity": pd.severity,
            "reasons": json.loads(pd.reasons_json),
            "timestamp": action.created_at.isoformat() if action.created_at else None,
        }
        for action, pd in rows
    ]
