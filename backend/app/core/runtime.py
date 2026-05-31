"""PACT Runtime — production library-first interface for agent security.

Wraps all existing PACT services into a clean, reusable interface that
works WITHOUT FastAPI. Import directly for library usage.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import hash_payload
from app.models.run import Run
from app.services.passport import PassportService
from app.services.intent import IntentService
from app.services.capability import CapabilityService
from app.services.envelope import EnvelopeService
from app.services.provenance import ProvenanceService
from app.services.ledger import LedgerService
from app.services.gateway import GatewayService
from app.services.configurable_policy import ConfigurablePolicyService


class PactRuntime:
    """Production PACT runtime — library-first interface for agent security.

    Usage:
        runtime = PactRuntime(issuer_private_key, issuer_public_key)
        result = await runtime.create_run(db, agent_id="agent-1")
        ...
    """

    def __init__(
        self,
        issuer_private_key: Optional[str] = None,
        issuer_public_key: Optional[str] = None,
        storage: Any = None,
        key_manager=None,
    ) -> None:
        if key_manager is not None:
            km = key_manager
            # Use separate keys for passport and capability
            passport_priv, passport_pub = km.get_key('passport_issuer')
            cap_priv, cap_pub = km.get_key('capability_issuer')
        else:
            passport_priv = issuer_private_key
            passport_pub = issuer_public_key
            cap_priv = issuer_private_key
            cap_pub = issuer_public_key

        self.issuer_private_key = passport_priv
        self.issuer_public_key = passport_pub
        self.storage = storage

        # Initialize all services
        self.passport_service = PassportService(passport_priv, passport_pub)
        self.intent_service = IntentService()
        self.capability_service = CapabilityService(cap_priv, cap_pub)
        self.envelope_service = EnvelopeService()
        self.provenance_service = ProvenanceService()
        self.policy_service = ConfigurablePolicyService()
        self.ledger_service = LedgerService()
        self._tool_registry = self.policy_service.tool_registry
        self.gateway_service = GatewayService(
            passport_service=self.passport_service,
            intent_service=self.intent_service,
            capability_service=self.capability_service,
            envelope_service=self.envelope_service,
            provenance_service=self.provenance_service,
            policy_service=self.policy_service,
            ledger_service=self.ledger_service,
            tool_registry=self._tool_registry,
        )

    # --- Tool Registration ---

    def register_tool(
        self,
        tool_id: str,
        metadata: dict[str, Any],
        fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        """Register an application tool with PACT enforcement metadata.

        Library and framework integrations should register tools here before
        executing them.  The gateway uses this metadata as the authoritative
        source for side effects, sensitivity, approval defaults, and output
        provenance.
        """
        self._tool_registry.register_tool(tool_id, metadata, fn=fn)

    # --- Run Management ---

    async def create_run(
        self,
        db: AsyncSession,
        agent_id: str,
        scenario_name: Optional[str] = None,
        user_goal: Optional[str] = None,
    ) -> dict:
        """Create a new execution run.

        Returns run metadata dict with run_id.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run = Run(
            run_id=run_id,
            agent_id=agent_id,
            scenario_name=scenario_name,
            user_goal=user_goal,
            status="running",
        )
        db.add(run)
        await db.commit()

        # Initialize provenance tracking
        self.provenance_service.start_run(run_id)

        return {
            "run_id": run_id,
            "agent_id": agent_id,
            "scenario_name": scenario_name,
            "user_goal": user_goal,
            "status": "running",
        }

    # --- Intent Management ---

    async def create_intent(
        self,
        db: AsyncSession,
        user_goal: str,
        created_by: str = "system",
        allowed_actions: Optional[list[str]] = None,
        forbidden_actions: Optional[list[str]] = None,
        resource_scope: Optional[dict] = None,
    ) -> dict:
        """Create an intent contract.

        If allowed_actions/forbidden_actions are provided, creates a programmatic
        intent (bypasses keyword classification). Otherwise uses the existing
        keyword-based classification.

        `resource_scope` is the operator-authorized resource allowlist and is
        folded into the intent hash so the authorized scope is tamper-evident.
        """
        resource_scope = resource_scope or {}
        if allowed_actions is not None or forbidden_actions is not None:
            # Programmatic intent — explicit allowed/forbidden actions
            allowed = allowed_actions or []
            forbidden = forbidden_actions or []

            # Generate hash from canonical form
            hash_input = {
                "user_goal": user_goal,
                "allowed_actions": sorted(allowed),
                "forbidden_actions": sorted(forbidden),
                "resource_scope": json.dumps(resource_scope, sort_keys=True),
                "risk_budget": "medium",
                "created_by": created_by,
            }
            intent_hash = hash_payload(hash_input)

            # Upsert: return existing if hash already exists
            from sqlalchemy import select
            from app.models.intent import Intent

            result = await db.execute(select(Intent).where(Intent.intent_hash == intent_hash))
            existing = result.scalars().first()
            if existing:
                return {
                    "intent_id": existing.intent_id,
                    "user_goal": existing.user_goal,
                    "allowed_actions": json.loads(existing.allowed_actions_json),
                    "forbidden_actions": json.loads(existing.forbidden_actions_json),
                    "resource_scope": json.loads(existing.resource_scope_json or "{}"),
                    "approval_required_for": json.loads(existing.approval_required_for_json),
                    "risk_budget": existing.risk_budget,
                    "intent_hash": existing.intent_hash,
                    "created_at": existing.created_at,
                    "created_by": existing.created_by,
                }

            intent_id = f"intent_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)

            intent = Intent(
                intent_id=intent_id,
                user_goal=user_goal,
                allowed_actions_json=json.dumps(allowed),
                forbidden_actions_json=json.dumps(forbidden),
                resource_scope_json=json.dumps(resource_scope),
                approval_required_for_json=json.dumps([]),
                risk_budget="medium",
                intent_hash=intent_hash,
                created_by=created_by,
            )
            db.add(intent)
            await db.commit()

            return {
                "intent_id": intent_id,
                "user_goal": user_goal,
                "allowed_actions": allowed,
                "forbidden_actions": forbidden,
                "resource_scope": resource_scope,
                "approval_required_for": [],
                "risk_budget": "medium",
                "intent_hash": intent_hash,
                "created_at": now,
                "created_by": created_by,
            }
        else:
            # Keyword classification (existing behavior)
            return await self.intent_service.create_intent(
                db, user_goal, created_by=created_by, resource_scope=resource_scope
            )

    # --- Capability Tokens ---

    async def issue_capability(
        self,
        db: AsyncSession,
        agent_id: str,
        intent_hash: str,
        capability: str,
        resource: str = "default",
        max_uses: int = 5,
        ttl_seconds: int = 300,
    ) -> dict:
        """Issue a signed capability token for a specific capability/resource."""
        return await self.capability_service.issue_token(
            db=db,
            agent_id=agent_id,
            intent_hash=intent_hash,
            capability=capability,
            resource=resource,
            max_uses=max_uses,
            ttl_seconds=ttl_seconds,
        )

    # --- Action Proposals ---

    async def propose_action(
        self,
        db: AsyncSession,
        run_id: str,
        agent_id: str,
        agent_private_key: str,
        tool: str,
        args: dict,
        intent_hash: str,
        capability_token_hash: str,
        provenance: Optional[dict] = None,
        step_id: Optional[int] = None,
        parent_action_hash: Optional[str] = None,
    ) -> dict:
        """Create an envelope and evaluate via gateway WITHOUT executing the tool.

        This is the dry-run / propose path. The gateway still runs all checks
        (passport, signature, capability, intent, policy), but it does not
        append to the ledger, consume the capability token, or invoke the tool.

        Returns dict with decision, action_hash, reasons, etc.
        """
        # Build provenance if not provided
        if provenance is None:
            self.provenance_service.ensure_run(run_id)
            self.provenance_service.record_step(run_id, tool, step_id=step_id or 0)
            provenance = self.provenance_service.build_provenance(run_id, tool)

        # Auto-compute step_id if not provided
        if step_id is None:
            chain = await self.ledger_service.get_chain(db, run_id)
            step_id = len(chain)

        # Create envelope
        envelope = self.envelope_service.create_envelope(
            agent_id=agent_id,
            agent_private_key=agent_private_key,
            run_id=run_id,
            step_id=step_id,
            tool=tool,
            args=args,
            intent_hash=intent_hash,
            capability_token_hash=capability_token_hash,
            provenance=provenance,
            parent_action_hash=parent_action_hash,
        )

        # Evaluate through gateway — dry_run: no ledger, no tool execution, no token consumption
        response = await self.gateway_service.execute(db, envelope, run_id, dry_run=True)

        return {
            "decision": response.decision.value,
            "risk_score": response.risk_score,
            "severity": response.severity.value,
            "reasons": response.reasons,
            "tool_result": response.tool_result,
            "action_hash": response.action_hash,
            "run_id": response.run_id,
            "envelope": envelope,
        }

    # --- Direct Evaluation (dry-run) ---

    async def evaluate_action(
        self,
        db: AsyncSession,
        run_id: str,
        agent_id: str,
        tool: str,
        args: dict,
        intent_hash: str,
        capability_token_hash: str,
        provenance: Optional[dict] = None,
        step_id: Optional[int] = None,
        parent_action_hash: Optional[str] = None,
        agent_private_key: Optional[str] = None,
    ) -> dict:
        """Evaluate an action through policy WITHOUT executing the tool.

        This is the true 'propose' path. It builds an envelope and runs it
        through passport/sig/cap/intent/policy checks, but it does not append
        to the ledger, consume the capability token, or execute the tool.

        When *agent_private_key* is provided the envelope is signed (needed for
        ALLOW decisions).  Without a key the envelope is left unsigned and the
        policy engine will BLOCK it.
        """
        # Build provenance if not provided
        if provenance is None:
            self.provenance_service.ensure_run(run_id)
            self.provenance_service.record_step(run_id, tool, step_id=step_id or 0)
            provenance = self.provenance_service.build_provenance(run_id, tool)

        # Auto-compute step_id if not provided
        if step_id is None:
            chain = await self.ledger_service.get_chain(db, run_id)
            step_id = len(chain)

        # Build envelope — sign when a key is provided
        args_digest = hash_payload(args)
        envelope = {
            'protocol': 'PACT/0.1',
            'run_id': run_id,
            'step_id': step_id,
            'agent_id': agent_id,
            'tool': tool,
            'args': args,
            'args_digest': args_digest,
            'intent_hash': intent_hash,
            'capability_token_hash': capability_token_hash,
            'provenance': provenance,
            'parent_action_hash': parent_action_hash,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'agent_signature': '',
        }

        if agent_private_key is not None:
            envelope = self.envelope_service.create_envelope(
                agent_id=agent_id,
                agent_private_key=agent_private_key,
                run_id=run_id,
                step_id=step_id,
                tool=tool,
                args=args,
                intent_hash=intent_hash,
                capability_token_hash=capability_token_hash,
                provenance=provenance,
                parent_action_hash=parent_action_hash,
            )

        # Use gateway dry_run: no ledger, no tool execution, no token consumption
        response = await self.gateway_service.execute(db, envelope, run_id, dry_run=True)

        return {
            'decision': response.decision.value,
            'risk_score': response.risk_score,
            'severity': response.severity.value,
            'reasons': response.reasons,
            'action_hash': response.action_hash,
            'run_id': response.run_id,
            'envelope': envelope,
        }

    # --- Full Execution ---

    async def execute_action(
        self,
        db: AsyncSession,
        envelope: dict,
        run_id: str,
    ) -> dict:
        """Full execute through gateway (evaluate + tool exec + ledger)."""
        response = await self.gateway_service.execute(db, envelope, run_id)
        return {
            "decision": response.decision.value,
            "risk_score": response.risk_score,
            "severity": response.severity.value,
            "reasons": response.reasons,
            "tool_result": response.tool_result,
            "action_hash": response.action_hash,
            "run_id": response.run_id,
        }

    async def execute_tool(
        self,
        db: AsyncSession,
        run_id: str,
        agent_id: str,
        agent_private_key: str,
        tool: str,
        args: dict,
        intent_hash: str,
        capability_token_hash: str,
        provenance: Optional[dict] = None,
        step_id: Optional[int] = None,
        parent_action_hash: Optional[str] = None,
    ) -> dict:
        """Create a signed envelope and execute a registered tool via gateway.

        This is the library-first call path for external agent runtimes.  It
        performs the complete PACT flow: passport, signature, intent,
        capability, policy, ledger append, token consumption, and tool result
        persistence.
        """
        if provenance is None:
            self.provenance_service.ensure_run(run_id)

        if step_id is None:
            chain = await self.ledger_service.get_chain(db, run_id)
            step_id = len(chain)
            if parent_action_hash is None and chain:
                parent_action_hash = chain[-1]["action_hash"]

        envelope = self.envelope_service.create_envelope(
            agent_id=agent_id,
            agent_private_key=agent_private_key,
            run_id=run_id,
            step_id=step_id,
            tool=tool,
            args=args,
            intent_hash=intent_hash,
            capability_token_hash=capability_token_hash,
            provenance=provenance or {},
            parent_action_hash=parent_action_hash,
        )

        return await self.execute_action(db=db, envelope=envelope, run_id=run_id)

    # --- Tool Result Recording ---

    async def record_tool_result(
        self,
        db: AsyncSession,
        action_hash: str,
        result: dict,
    ) -> None:
        """Record the result of an externally-executed tool."""
        from sqlalchemy import update as sa_update
        from app.models.action import Action
        from app.core.result_sanitizer import strip_sensitive_fields
        await db.execute(
            sa_update(Action)
            .where(Action.action_hash == action_hash)
            .values(result_json=json.dumps(strip_sensitive_fields(result)))
        )
        await db.commit()

    # --- Model Events ---

    async def record_model_event(
        self,
        db: AsyncSession,
        run_id: str,
        provider: str,
        model: str,
        request_json: str,
        response_json: str,
        tool_calls: Optional[list] = None,
        token_usage: Optional[dict] = None,
    ) -> dict:
        """Record a model interaction event."""
        from app.models.model_event import ModelEvent

        event_id = f"mevt_{uuid.uuid4().hex[:12]}"
        event = ModelEvent(
            run_id=run_id,
            event_id=event_id,
            provider=provider,
            model=model,
            request_json=request_json,
            response_json=response_json,
            tool_calls_json=json.dumps(tool_calls) if tool_calls else None,
            token_usage_json=json.dumps(token_usage) if token_usage else None,
        )
        db.add(event)
        await db.commit()

        return {
            "event_id": event_id,
            "run_id": run_id,
            "provider": provider,
            "model": model,
        }

    # --- Ledger Verification ---

    async def verify_run(
        self,
        db: AsyncSession,
        run_id: str,
    ) -> dict:
        """Verify ledger integrity for a run."""
        valid, issues = await self.ledger_service.verify_chain(db, run_id)
        chain = await self.ledger_service.get_chain(db, run_id)
        return {
            "run_id": run_id,
            "valid": valid,
            "issues": issues,
            "chain_length": len(chain),
        }

    # --- Agent Passport Registration ---

    async def register_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        owner: str,
        agent_type: str,
        allowed_domains: list[str],
        risk_tier: str = "medium",
        ttl_days: int = 30,
    ) -> dict:
        """Register an agent passport.

        Returns passport data including the agent's private key (return once;
        caller must store it).
        """
        return await self.passport_service.create_passport(
            db=db,
            agent_id=agent_id,
            owner=owner,
            agent_type=agent_type,
            allowed_domains=allowed_domains,
            risk_tier=risk_tier,
            ttl_days=ttl_days,
        )
