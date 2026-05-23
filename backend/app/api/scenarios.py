"""Scenario and Run API routes."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.run import Run
from app.models.action import Action
from app.models.policy_decision import PolicyDecision as PolicyDecisionModel
from app.schemas import (
    ScenarioInfo,
    ScenarioRunResponse,
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
from app.services.scenarios import list_scenarios, get_scenario

router = APIRouter()


@router.get("", response_model=list[ScenarioInfo])
async def get_scenarios():
    """List all available demo scenarios."""
    scenarios = list_scenarios()
    return [ScenarioInfo(**s) for s in scenarios]


@router.post("/run/{scenario_name}", response_model=ScenarioRunResponse)
async def run_scenario(
    scenario_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Execute a demo scenario through the full PACT pipeline."""
    scenario = get_scenario(scenario_name)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_name}' not found")

    # Build runtime with fresh services
    from app.crypto import generate_keypair
    from app.services.passport import PassportService
    from app.services.intent import IntentService
    from app.services.capability import CapabilityService
    from app.services.envelope import EnvelopeService
    from app.services.provenance import ProvenanceService
    from app.services.policy import PolicyService
    from app.services.ledger import LedgerService
    from app.services.gateway import GatewayService
    from app.services.runtime import RuntimeService

    issuer_private, issuer_public = generate_keypair()

    passport_svc = PassportService(issuer_private, issuer_public)
    intent_svc = IntentService()
    capability_svc = CapabilityService(issuer_private, issuer_public)
    envelope_svc = EnvelopeService()
    provenance_svc = ProvenanceService()
    policy_svc = PolicyService()
    ledger_svc = LedgerService()

    gateway_svc = GatewayService(
        passport_service=passport_svc,
        intent_service=intent_svc,
        capability_service=capability_svc,
        envelope_service=envelope_svc,
        provenance_service=provenance_svc,
        policy_service=policy_svc,
        ledger_service=ledger_svc,
    )

    runtime = RuntimeService(
        passport_service=passport_svc,
        intent_service=intent_svc,
        capability_service=capability_svc,
        envelope_service=envelope_svc,
        provenance_service=provenance_svc,
        gateway_service=gateway_svc,
        ledger_service=ledger_svc,
    )

    result = await runtime.run_scenario(db, scenario_name)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return ScenarioRunResponse(
        run_id=result["run_id"],
        scenario_name=result["scenario_name"],
        status=RunStatus.COMPLETED,
        total_actions=result["total_actions"],
        allowed_actions=result["allowed_actions"],
        blocked_actions=result["blocked_actions"],
        max_risk_score=result["max_risk_score"],
    )
