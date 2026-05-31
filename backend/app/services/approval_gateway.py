"""Extended gateway that integrates the approval workflow with the PACT gateway.

This module wraps :class:`GatewayService` without modifying it.  When the
gateway returns ``REQUIRE_APPROVAL``, an approval record is created that a
human reviewer can later approve or deny.

When resuming an approved action, the envelope digest is verified against
the stored approved_envelope_digest to prevent tampering.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import Decision
from app.services.gateway import GatewayService
from app.services.approval import ApprovalService


class ApprovalGatewayService:
    """Extended gateway that handles approval flow.

    Wraps the core ``GatewayService`` and automatically creates approval
    records when the policy decision is ``REQUIRE_APPROVAL``.
    """

    def __init__(
        self,
        gateway: GatewayService,
        approval_service: ApprovalService,
    ):
        self.gateway = gateway
        self.approval_service = approval_service

    async def execute_with_approval(
        self,
        db: AsyncSession,
        envelope: dict,
        run_id: str,
    ) -> dict:
        """Execute through the gateway.

        If the policy returns ``REQUIRE_APPROVAL``, an approval record is
        created and its ``approval_id`` is included in the response.
        """
        response = await self.gateway.execute(db, envelope, run_id)

        if response.decision == Decision.REQUIRE_APPROVAL:
            approval = await self.approval_service.create_approval(
                db=db,
                run_id=run_id,
                action_hash=response.action_hash or "",
                agent_id=envelope.get("agent_id", ""),
                envelope_json=json.dumps(envelope),
            )
            return {
                "decision": "REQUIRE_APPROVAL",
                "approval_id": approval["approval_id"],
                "action_hash": response.action_hash,
                "run_id": run_id,
                "reasons": response.reasons,
            }

        return {
            "decision": response.decision.value,
            "action_hash": response.action_hash,
            "run_id": run_id,
            "reasons": response.reasons,
            "tool_result": response.tool_result,
            "risk_score": response.risk_score,
            "severity": response.severity.value,
        }

    async def resume_approved(
        self,
        db: AsyncSession,
        approval_id: str,
        decided_by: str,
    ) -> dict:
        """Execute an action whose approval has been granted.

        Verifies that the re-submitted envelope matches the approved envelope
        digest, then re-executes through the gateway with skip_approval=True.
        """
        approval = await self.approval_service.get_approval(db, approval_id)
        if not approval:
            return {"error": "Approval not found"}
        if approval["status"] != "approved":
            return {
                "error": f"Approval status is {approval['status']}, not approved",
            }

        envelope_json = approval.get("envelope_json", "")
        envelope = json.loads(envelope_json)

        # Verify envelope integrity: re-submitted envelope must match approved digest
        stored_digest = approval.get("approved_envelope_digest")
        if stored_digest:
            recomputed = hashlib.sha256(envelope_json.encode()).hexdigest()
            if recomputed != stored_digest:
                return {
                    "error": "Envelope tampered: digest does not match approved envelope",
                }

        # skip_approval=True prevents the gateway from returning REQUIRE_APPROVAL
        # again for this already-approved action.
        response = await self.gateway.execute(
            db, envelope, approval["run_id"], skip_approval=True,
        )
        return {
            "decision": response.decision.value,
            "action_hash": response.action_hash,
            "run_id": approval["run_id"],
            "approval_id": approval_id,
        }
