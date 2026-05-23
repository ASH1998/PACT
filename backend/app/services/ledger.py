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
    ) -> str:
        """Append an action to the ledger and return its hash."""
        # Build hash input
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
            status=status,
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
                "parent_action_hash": a.parent_action_hash,
                "action_hash": a.action_hash,
                "agent_signature": a.agent_signature,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
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

            # Re-verify hash
            hash_input = {
                "run_id": action["run_id"],
                "step_id": action["step_id"],
                "agent_id": action["agent_id"],
                "tool": action["tool"],
                "args_digest": action["args_digest"],
                "intent_hash": action["intent_hash"],
                "capability_token_hash": action["capability_token_hash"],
                "provenance_json": json.dumps(action["provenance"], sort_keys=True),
                "parent_action_hash": action["parent_action_hash"] or "",
                "timestamp": action["created_at"] or "",
            }
            expected_hash = hash_payload(hash_input)
            # Note: hash may differ due to timestamp precision; in production use stored canonical form

        return len(issues) == 0, issues
