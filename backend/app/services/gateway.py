"""Gateway Service — the core trust boundary. Rejects raw tool calls, only accepts signed PACT envelopes."""

import inspect
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import Decision, Severity, ToolCallResponse, PolicyDecision
from app.services.passport import PassportService
from app.services.intent import IntentService
from app.services.capability import CapabilityService
from app.services.envelope import EnvelopeService
from app.services.provenance import ProvenanceService
from app.services.policy import PolicyService
from app.services.ledger import LedgerService
from app.tools import get_mock_tool
from app.tools.resource import resource_from_args, resource_in_scope


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
        tool_registry=None,
    ):
        self.passport_service = passport_service
        self.intent_service = intent_service
        self.capability_service = capability_service
        self.envelope_service = envelope_service
        self.provenance_service = provenance_service
        self.policy_service = policy_service
        self.ledger_service = ledger_service
        self._tool_registry = tool_registry

    async def execute(
        self,
        db: AsyncSession,
        envelope: dict,
        run_id: str,
        dry_run: bool = False,
        skip_approval: bool = False,
    ) -> ToolCallResponse:
        """Execute a tool call through the PACT gateway.

        This is the core trust boundary. Every tool call must pass through here.

        When dry_run=True, evaluates policy and returns the decision without
        appending to the ledger, consuming capability tokens, or executing tools.
        Useful for propose/evaluate paths that need policy verdicts without side effects.

        When skip_approval=True, if the policy would return REQUIRE_APPROVAL,
        the decision is overridden to ALLOW. Used by resume_approved() to prevent
        approval loops on already-approved actions.
        """
        agent_id = envelope.get("agent_id")
        tool = envelope.get("tool")
        step_id = envelope.get("step_id", 0)
        parent_action_hash = envelope.get("parent_action_hash")
        agent_signature = envelope.get("agent_signature", "")

        # Build server-side provenance (trust boundary — never trust agent-declared labels)
        self.provenance_service.ensure_run(run_id)
        args = envelope.get("args", {})
        self.provenance_service.record_step(run_id, tool, step_id=step_id, resource=resource_from_args(tool, args))
        provenance = self.provenance_service.build_provenance(run_id, tool)

        # Step 1: Verify agent passport
        passport = await self.passport_service.get_passport(db, agent_id)
        if not passport:
            if dry_run:
                return ToolCallResponse(
                    decision=Decision.BLOCK, risk_score=100, severity="critical",
                    reasons=["Agent not registered: no passport found"],
                    action_hash="dry_run", run_id=run_id,
                )
            # No passport — record in ledger
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

        # Step 3b: Verify intent ownership — agent can only use intents it created
        if intent and intent.get("created_by") not in (agent_id, "system"):
            if dry_run:
                return ToolCallResponse(
                    decision=Decision.BLOCK, risk_score=100, severity=Severity.CRITICAL,
                    reasons=["Intent ownership mismatch: agent did not create this intent"],
                    action_hash="dry_run", run_id=run_id,
                )
            # Agent is claiming an intent it doesn't own — block
            from app.models.policy_decision import PolicyDecision as PolicyDecisionModel
            action_hash = await self.ledger_service.append_action(
                db=db, run_id=run_id, step_id=step_id, agent_id=agent_id, tool=tool,
                args_digest=envelope.get("args_digest", ""), intent_hash=envelope.get("intent_hash", ""),
                capability_token_hash=envelope.get("capability_token_hash", ""),
                provenance=provenance, parent_action_hash=parent_action_hash,
                agent_signature=agent_signature, status="blocked",
            )
            pd_record = PolicyDecisionModel(
                run_id=run_id, action_hash=action_hash, decision="BLOCK",
                risk_score=100, severity="critical",
                reasons_json='["Intent ownership mismatch: agent did not create this intent"]',
            )
            db.add(pd_record)
            await db.commit()
            return ToolCallResponse(
                decision=Decision.BLOCK, risk_score=100, severity=Severity.CRITICAL,
                reasons=["Intent ownership mismatch: agent did not create this intent"],
                action_hash=action_hash, run_id=run_id,
            )

        # Step 4: Validate capability token
        cap_valid = True
        cap_reason = "Valid"
        token_hash = envelope.get("capability_token_hash", "")
        if intent:
            # Extract resource from args for validation
            args = envelope.get("args", {})
            # Resource binding: the token is bound to a resource extracted from the envelope args.
            # In the demo, the resource is self-declared by the caller at issue time.
            # A production system would verify this against a user-authorized resource scope.
            resource = resource_from_args(tool, args)
            cap_valid, cap_reason = await self.capability_service.validate_token(
                db, token_hash, agent_id, envelope.get("intent_hash", ""), tool, resource=resource
            )

        # Step 4b: Resource scope check — the requested resource (proposed by the
        # agent via args) must fall within the operator-authorized scope on the
        # intent contract. Default-deny for scoped resource types.
        req_resource = resource_from_args(tool, args)
        resource_type = "default"
        if self._tool_registry is not None:
            tool_entry = self._tool_registry.get_tool(tool)
            if tool_entry:
                resource_type = tool_entry["metadata"].get("resource_type", "default")
        # Resource scoping is opt-in per intent: an intent with no resource_scope
        # configured is not resource-restricted (preserves legacy/programmatic
        # intents). When a scope IS present, it is enforced default-deny per type.
        intent_scope = intent.get("resource_scope", {}) if intent else {}
        res_in_scope = (
            resource_in_scope(resource_type, req_resource, intent_scope)
            if intent_scope
            else True
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
            resource=req_resource,
            resource_in_scope=res_in_scope,
        )

        # Step 5b: Override REQUIRE_APPROVAL if skip_approval is set (already approved)
        if skip_approval and policy_decision.decision == Decision.REQUIRE_APPROVAL:
            policy_decision = PolicyDecision(
                decision=Decision.ALLOW,
                risk_score=policy_decision.risk_score,
                severity=policy_decision.severity,
                reasons=["Pre-approved: human reviewer already approved this action"],
            )

        # Step 6: Determine action status
        if policy_decision.decision == Decision.ALLOW:
            action_status = "allowed"
        elif policy_decision.decision == Decision.BLOCK:
            action_status = "blocked"
        else:
            action_status = "pending_approval"

        # In dry_run mode, return the policy verdict without any side effects
        if dry_run:
            from app.crypto import hash_payload as _hash
            synthetic_hash = f"dry_{_hash(envelope)[:16]}"
            return ToolCallResponse(
                decision=policy_decision.decision,
                risk_score=policy_decision.risk_score,
                severity=policy_decision.severity,
                reasons=policy_decision.reasons,
                tool_result=None,
                action_hash=synthetic_hash,
                run_id=run_id,
            )

        # Steps 7-9: persist to ledger, execute tool, consume token, record decision
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

        # Step 8: If ALLOW, execute the tool via registry
        tool_result = None
        if policy_decision.decision == Decision.ALLOW:
            tool_fn = None
            if self._tool_registry is not None:
                tool_fn = self._tool_registry.get_callable(tool)
            if tool_fn is None:
                # Fallback to legacy mock tools for backward compat
                tool_fn = get_mock_tool(tool)
            if tool_fn:
                args = envelope.get("args", {})
                tool_result = tool_fn(**args)
                if inspect.isawaitable(tool_result):
                    tool_result = await tool_result
        # Persist tool result back to the action record
        if tool_result is not None:
            from app.models.action import Action as ActionModel
            from sqlalchemy import update as sa_update
            await db.execute(
                sa_update(ActionModel)
                .where(ActionModel.action_hash == action_hash)
                .values(result_json=json.dumps(tool_result))
            )

        # Step 8.5: Always consume a use (prevents infinite probing)
        if token_hash:
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
