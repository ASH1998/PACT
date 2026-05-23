from __future__ import annotations
"""Runtime Service — executes deterministic demo scenarios through the PACT gateway."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.gateway import GatewayService
from app.services.passport import PassportService
from app.services.intent import IntentService
from app.services.capability import CapabilityService
from app.services.envelope import EnvelopeService
from app.services.provenance import ProvenanceService
from app.services.ledger import LedgerService
from app.services.scenarios import get_scenario
from app.models.run import Run
from app.tools.resource import resource_from_args


class RuntimeService:
    """Executes deterministic demo scenarios end-to-end through the PACT pipeline."""

    def __init__(
        self,
        passport_service: PassportService,
        intent_service: IntentService,
        capability_service: CapabilityService,
        envelope_service: EnvelopeService,
        provenance_service: ProvenanceService,
        gateway_service: GatewayService,
        ledger_service: LedgerService,
    ):
        self.passport_service = passport_service
        self.intent_service = intent_service
        self.capability_service = capability_service
        self.envelope_service = envelope_service
        self.provenance_service = provenance_service
        self.gateway_service = gateway_service
        self.ledger_service = ledger_service

    async def run_scenario(self, db: AsyncSession, scenario_name: str) -> dict:
        """Execute a named scenario and return the full run result."""
        scenario = get_scenario(scenario_name)
        if not scenario:
            return {"error": f"Unknown scenario: {scenario_name}"}

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        agent_id = f"{scenario['agent_id']}_{run_id}"
        user_goal = scenario["user_goal"]

        # Create run record
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

        # Always create a fresh passport for each scenario run.
        # Scenarios are deterministic demos, not persistent agents, so this
        # avoids the bug where an existing agent's private key is unavailable,
        # causing signature mismatches.
        agent_private_key = ""
        if scenario_name != "fake_agent_identity":
            result = await self.passport_service.create_passport(
                db=db,
                agent_id=agent_id,
                owner="team-pact",
                agent_type=scenario.get("agent_type", "assistant"),
                allowed_domains=scenario.get("allowed_domains", []),
                risk_tier="medium",
            )
            agent_private_key = result["agent_private_key"]

        # Create intent
        intent = await self.intent_service.create_intent(db, user_goal)
        intent_hash = intent["intent_hash"]

        # Execute each step
        responses = []
        parent_action_hash = None
        allowed_count = 0
        blocked_count = 0
        max_risk = 0

        for i, step in enumerate(scenario["steps"]):
            tool = step["tool"]
            args = step.get("args", {})

            # Record provenance
            self.provenance_service.record_step(run_id, tool)
            provenance = self.provenance_service.build_provenance(run_id, tool)

            # Get the agent's private key (for demo, we re-read from the passport we just created)
            passport = await self.passport_service.get_passport(db, agent_id)
            if not passport and scenario_name == "fake_agent_identity":
                # Fake agent — use dummy keys
                from app.crypto import generate_keypair
                _, fake_private = generate_keypair()
                agent_private_key = fake_private
                passport = {"public_key": "fake"}

            # Issue capability token for this tool
            token = await self.capability_service.issue_token(
                db=db,
                agent_id=agent_id,
                intent_hash=intent_hash,
                capability=tool,
                resource=resource_from_args(tool, args),
                max_uses=3,
                ttl_seconds=300 if not step.get("expire_token") else 0,
            )

            # For expired token scenario, wait a moment
            if step.get("expire_token"):
                # Force-expire the token by setting expires_at in the past
                from sqlalchemy import update
                from app.models.capability import CapabilityToken as CapModel
                await db.execute(
                    update(CapModel)
                    .where(CapModel.token_hash == token["token_hash"])
                    .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
                )
                await db.commit()

            # Create envelope
            envelope = self.envelope_service.create_envelope(
                agent_id=agent_id,
                agent_private_key=agent_private_key,
                run_id=run_id,
                step_id=i,
                tool=tool,
                args=args,
                intent_hash=intent_hash,
                capability_token_hash=token["token_hash"],
                provenance=provenance,
                parent_action_hash=parent_action_hash,
            )

            # Execute through gateway
            response = await self.gateway_service.execute(db, envelope, run_id)
            responses.append({
                "step_id": i,
                "tool": tool,
                "args": args,
                "decision": response.decision.value,
                "risk_score": response.risk_score,
                "severity": response.severity.value,
                "reasons": response.reasons,
                "tool_result": response.tool_result,
                "action_hash": response.action_hash,
                "provenance": provenance,
            })

            parent_action_hash = response.action_hash
            max_risk = max(max_risk, response.risk_score)

            if response.decision.value == "ALLOW":
                allowed_count += 1
            else:
                blocked_count += 1

            # If blocked, stop the scenario
            if response.decision.value == "BLOCK":
                break

        # Update run record
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "run_id": run_id,
            "scenario_name": scenario_name,
            "user_goal": user_goal,
            "agent_id": agent_id,
            "status": "completed",
            "total_actions": len(responses),
            "allowed_actions": allowed_count,
            "blocked_actions": blocked_count,
            "max_risk_score": max_risk,
            "steps": responses,
        }
