"""V1 Gateway API — submit a client-signed Action Envelope for enforcement.

This is the path for external (non-Python) agent clients such as the Go TUI.
The client builds and signs the envelope itself, submits it here, and the
gateway runs the full trust boundary (passport, signature, capability, intent,
resource scope, provenance, policy), records the decision and ledger entry, and
consumes the capability — but does NOT execute the tool server-side. The client
executes the tool locally and attaches the result via
``POST /v1/actions/{action_hash}/result``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


class GatewayExecuteRequest(BaseModel):
    run_id: str
    envelope: dict
    skip_approval: bool = False


@router.post("/execute")
async def gateway_execute(req: GatewayExecuteRequest, db: AsyncSession = Depends(get_db)):
    """Run a client-signed envelope through the gateway without server-side tool
    execution. Returns the authoritative PACT decision and the recorded
    action_hash so the client can attach its locally-produced tool result."""
    from app.core.factory import get_runtime

    runtime = get_runtime()
    response = await runtime.gateway_service.execute(
        db,
        req.envelope,
        req.run_id,
        skip_approval=req.skip_approval,
        execute_tool=False,
    )
    return {
        "decision": response.decision.value,
        "risk_score": response.risk_score,
        "severity": response.severity.value,
        "reasons": response.reasons,
        "action_hash": response.action_hash,
        "run_id": response.run_id,
    }
