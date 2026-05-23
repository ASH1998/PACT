"""Tools API route — execute tools through the PACT gateway."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ToolCallRequest, ToolCallResponse
from app.crypto.issuer import ISSUER_PRIVATE_KEY, ISSUER_PUBLIC_KEY
from app.services.passport import PassportService
from app.services.intent import IntentService
from app.services.capability import CapabilityService
from app.services.envelope import EnvelopeService
from app.services.provenance import ProvenanceService
from app.services.policy import PolicyService
from app.services.ledger import LedgerService
from app.services.gateway import GatewayService

router = APIRouter()


@router.post("/call", response_model=ToolCallResponse)
async def call_tool(
    req: ToolCallRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a tool call through the PACT gateway.

    This endpoint only accepts PACT Action Envelopes.
    Raw tool calls are rejected.
    """
    # The envelope must be present
    if not req.envelope:
        raise HTTPException(status_code=400, detail="PACT Action Envelope required")

    envelope = req.envelope

    # Create or find run
    run_id = req.run_id or req.envelope.get("run_id", "")
    if not run_id:
        run_id = f"run_{uuid.uuid4().hex[:12]}"

    # Create run record if it doesn't exist
    from sqlalchemy import select
    from app.models.run import Run

    existing = await db.execute(select(Run).where(Run.run_id == run_id))
    if not existing.scalar_one_or_none():
        run = Run(run_id=run_id, agent_id=envelope.get("agent_id", "unknown"), status="running")
        db.add(run)
        await db.commit()

    # Create all services with stable issuer keys
    passport_svc = PassportService(ISSUER_PRIVATE_KEY, ISSUER_PUBLIC_KEY)
    intent_svc = IntentService()
    capability_svc = CapabilityService(ISSUER_PRIVATE_KEY, ISSUER_PUBLIC_KEY)
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

    response = await gateway_svc.execute(db, envelope, run_id)

    # Update run status
    from datetime import datetime, timezone

    result = await db.execute(select(Run).where(Run.run_id == run_id))
    run_record = result.scalar_one_or_none()
    if run_record:
        run_record.status = "completed"
        run_record.completed_at = datetime.now(timezone.utc)
        await db.commit()

    return response
