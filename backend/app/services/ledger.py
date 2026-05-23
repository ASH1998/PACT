from __future__ import annotations
"""Ledger Service — tamper-evident hash-chain of all actions."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import canonical_json, hash_payload
from app.models.action import Action


class LedgerService:
    """Maintains a hash-chained ledger of all attempted actions."""

    async def append_action(
        self,
        db: AsyncSession,
        run_id: str,
        step_id: int,
        agent_id: str,
        tool: str,
        args_digest: str,
        intent_hash: str,
        capability_token_hash: str,
        provenance: dict,
        parent_action_hash: str | None,
        agent_signature: str,
        status: str = "allowed",
        args_json: str = "{}",
        envelope_timestamp: str | None = None,
    ) -> str:
        """Append an action to the ledger and return its hash."""
        # Build hash input
        # Use envelope_timestamp if provided, otherwise generate server-side
        ts = envelope_timestamp or datetime.now(timezone.utc).isoformat()

        hash_input = {
            "run_id": run_id,
            "step_id": step_id,
            "agent_id": agent_id,
            "tool": tool,
            "args_digest": args_digest,
            "intent_hash": intent_hash,
            "capability_token_hash": capability_token_hash,
            "provenance_json": json.dumps(provenance, sort_keys=True),
            "parent_action_hash": parent_action_hash or "",
            "timestamp": ts,
        }
        action_hash = hash_payload(hash_input)

        # Store
        action = Action(
            run_id=run_id,
            step_id=step_id,
            agent_id=agent_id,
            tool=tool,
            args_digest=args_digest,
            intent_hash=intent_hash,
            capability_token_hash=capability_token_hash,
            provenance_json=json.dumps(provenance),
            parent_action_hash=parent_action_hash,
            action_hash=action_hash,
            agent_signature=agent_signature,
            hash_input_json=json.dumps(hash_input, sort_keys=True),
            status=status,
            args_json=args_json,
            envelope_timestamp=ts,
        )
        db.add(action)
        await db.commit()

        return action_hash

    async def get_chain(self, db: AsyncSession, run_id: str) -> list[dict]:
        """Get all actions for a run in order."""
        result = await db.execute(
            select(Action)
            .where(Action.run_id == run_id)
            .order_by(Action.step_id)
        )
        actions = result.scalars().all()

        return [
            {
                "run_id": a.run_id,
                "step_id": a.step_id,
                "agent_id": a.agent_id,
                "tool": a.tool,
                "args_digest": a.args_digest,
                "intent_hash": a.intent_hash,
                "capability_token_hash": a.capability_token_hash,
                "provenance": json.loads(a.provenance_json),
                "provenance_json": a.provenance_json,
                "parent_action_hash": a.parent_action_hash,
                "action_hash": a.action_hash,
                "agent_signature": a.agent_signature,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "hash_input_json": a.hash_input_json,
                "args_json": a.args_json,
                "envelope_timestamp": a.envelope_timestamp,
            }
            for a in actions
        ]

    async def verify_chain(self, db: AsyncSession, run_id: str) -> tuple[bool, list[str]]:
        """Verify the hash chain integrity for a run. Returns (valid, issues)."""
        chain = await self.get_chain(db, run_id)
        issues: list[str] = []

        if not chain:
            return True, []

        for i, action in enumerate(chain):
            # Check parent linkage
            if i == 0:
                if action["parent_action_hash"] is not None:
                    issues.append(
                        f"Step {action['step_id']}: first action should have null parent"
                    )
            else:
                expected_parent = chain[i - 1]["action_hash"]
                if action["parent_action_hash"] != expected_parent:
                    issues.append(
                        f"Step {action['step_id']}: parent hash mismatch "
                        f"(expected {expected_parent[:20]}..., got {str(action['parent_action_hash'])[:20]}...)"
                    )

            # Reconstruct hash input from independently stored columns
            # (do NOT trust hash_input_json — it could be tampered alongside action fields)
            reconstructed_input = {
                "run_id": action["run_id"],
                "step_id": action["step_id"],
                "agent_id": action["agent_id"],
                "tool": action["tool"],
                "args_digest": action["args_digest"],
                "intent_hash": action["intent_hash"],
                "capability_token_hash": action["capability_token_hash"],
                "provenance_json": json.dumps(
                    json.loads(action["provenance_json"]) if isinstance(action["provenance_json"], str)
                    else action["provenance_json"],
                    sort_keys=True,
                ),
                "parent_action_hash": action["parent_action_hash"] or "",
                "timestamp": action["envelope_timestamp"] or "",
            }
            expected_hash = hash_payload(reconstructed_input)

            if action["action_hash"] != expected_hash:
                issues.append(
                    f"Step {action['step_id']}: hash mismatch "
                    f"(expected {expected_hash[:20]}..., got {action['action_hash'][:20]}...)"
                )

        return len(issues) == 0, issues
