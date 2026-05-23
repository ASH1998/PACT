"""Gateway Service — the core trust boundary. Rejects raw tool calls, only accepts signed PACT envelopes."""

import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import Decision, ToolCallResponse
from app.services.passport import PassportService
from app.services.intent import IntentService
from app.services.capability import CapabilityService
from app.services.envelope import EnvelopeService
from app.services.provenance import ProvenanceService
from app.services.policy import PolicyService
from app.services.ledger import LedgerService
from app.tools import get_mock_tool
from app.tools.resource import resource_from_args


class GatewayService:
    """Tool Gateway — the only path to execute tools. Enforces PACT protocol."""

    def __init__(
        self,
        passport_service: PassportService,
        intent_service: IntentService,
        capability_service: CapabilityService,
        envelope_service: EnvelopeService,
        provenance_service: ProvenanceService,
        policy_service: PolicyService,
        ledger_service: LedgerService,
    ):
        self.passport_service = passport_service
        self.intent_service = intent_service
        self.capability_service = capability_service
        self.envelope_service = envelope_service
        self.provenance_service = provenance_service
        self.policy_service = policy_service
        self.ledger_service = ledger_service

    async def execute(
        self,
        db: AsyncSession,
        envelope: dict,
        run_id: str,
    ) -> ToolCallResponse:
        """Execute a tool call through the PACT gateway.

        This is the core trust boundary. Every tool call must pass through here.
        """
        agent_id = envelope.get("agent_id")
        tool = envelope.get("tool")
        step_id = envelope.get("step_id", 0)
        provenance = envelope.get("provenance", {})
        parent_action_hash = envelope.get("parent_action_hash")
        agent_signature = envelope.get("agent_signature", "")

        # Step 1: Verify agent passport
        passport = await self.passport_service.get_passport(db, agent_id)
        if not passport:
            # No passport — compute dummy action_hash and record in ledger
            from app.models.policy_decision import PolicyDecision as PolicyDecisionModel

            action_hash = await self.ledger_service.append_action(
                db=db,
                run_id=run_id,
                step_id=step_id,
                agent_id=agent_id,
                tool=tool,
                args_digest=envelope.get("args_digest", ""),
                intent_hash=envelope.get("intent_hash", ""),
                capability_token_hash=envelope.get("capability_token_hash", ""),
                provenance=provenance,
                parent_action_hash=parent_action_hash,
                agent_signature=agent_signature,
                status="blocked",
            )

            pd_record = PolicyDecisionModel(
                run_id=run_id,
                action_hash=action_hash,
                decision="BLOCK",
                risk_score=100,
                severity="critical",
                reasons_json='["Agent not registered: no passport found"]',
            )
            db.add(pd_record)
            await db.commit()

            response = ToolCallResponse(
                decision=Decision.BLOCK,
                risk_score=100,
                severity="critical",
                reasons=["Agent not registered: no passport found"],
                action_hash=action_hash,
                run_id=run_id,
            )
            return response

        passport_valid, passport_reason = await self.passport_service.verify_passport(passport)
        agent_public_key = passport.get("public_key", "")

        # Step 2: Verify envelope signature
        sig_valid, sig_reason = self.envelope_service.verify_envelope(envelope, agent_public_key)

        # Step 3: Load intent contract
        intent = await self.intent_service.get_intent_by_hash(db, envelope.get("intent_hash", ""))
        allowed_actions = intent.get("allowed_actions", []) if intent else []
        forbidden_actions = intent.get("forbidden_actions", []) if intent else []

        # Step 4: Validate capability token
        cap_valid = True
        cap_reason = "Valid"
        token_hash = envelope.get("capability_token_hash", "")
        if intent:
            # Extract resource from args for validation
            args = envelope.get("args", {})
            resource = resource_from_args(tool, args)
            cap_valid, cap_reason = await self.capability_service.validate_token(
                db, token_hash, agent_id, envelope.get("intent_hash", ""), tool, resource=resource
            )

        # Step 5: Evaluate policy
        policy_decision = self.policy_service.evaluate(
            tool=tool,
            allowed_actions=allowed_actions,
            forbidden_actions=forbidden_actions,
            provenance=provenance,
            passport_valid=passport_valid,
            passport_reason=passport_reason,
            signature_valid=sig_valid,
            capability_valid=cap_valid,
            capability_reason=cap_reason,
        )

        # Step 6: Determine action status
        if policy_decision.decision == Decision.ALLOW:
            action_status = "allowed"
        elif policy_decision.decision == Decision.BLOCK:
            action_status = "blocked"
        else:
            action_status = "pending_approval"

        # Step 7: Append to ledger
        args_digest = envelope.get("args_digest", "")
        intent_hash = envelope.get("intent_hash", "")
        action_hash = await self.ledger_service.append_action(
            db=db,
            run_id=run_id,
            step_id=step_id,
            agent_id=agent_id,
            tool=tool,
            args_digest=args_digest,
            intent_hash=intent_hash,
            capability_token_hash=token_hash,
            provenance=provenance,
            parent_action_hash=parent_action_hash,
            agent_signature=agent_signature,
            status=action_status,
            args_json=json.dumps(envelope.get("args", {})),
            envelope_timestamp=envelope.get("timestamp", ""),
        )

        # Step 8: If ALLOW, execute the mock tool
        tool_result = None
        if policy_decision.decision == Decision.ALLOW:
            tool_fn = get_mock_tool(tool)
            if tool_fn:
                args = envelope.get("args", {})
                tool_result = tool_fn(**args)

            # Consume a capability use
            await self.capability_service.consume_use(db, token_hash)

        # Step 9: Record policy decision
        from app.models.policy_decision import PolicyDecision as PolicyDecisionModel

        pd_record = PolicyDecisionModel(
            run_id=run_id,
            action_hash=action_hash,
            decision=policy_decision.decision.value,
            risk_score=policy_decision.risk_score,
            severity=policy_decision.severity.value,
            reasons_json=json.dumps(policy_decision.reasons),
        )
        db.add(pd_record)
        await db.commit()

        return ToolCallResponse(
            decision=policy_decision.decision,
            risk_score=policy_decision.risk_score,
            severity=policy_decision.severity,
            reasons=policy_decision.reasons,
            tool_result=tool_result,
            action_hash=action_hash,
            run_id=run_id,
        )
