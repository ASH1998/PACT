"""Approval Service — manages human-in-the-loop approval workflow."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval


class ApprovalService:
    """Manages approval records for actions that require human approval."""

    async def create_approval(
        self,
        db: AsyncSession,
        run_id: str,
        action_hash: str,
        agent_id: str,
        envelope_json: str,
        ttl_seconds: int = 3600,
    ) -> dict:
        """Create a new pending approval record.

        Returns the approval record as a dict.
        """
        approval_id = f"appr_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        record = Approval(
            approval_id=approval_id,
            run_id=run_id,
            action_hash=action_hash,
            requested_by_agent_id=agent_id,
            envelope_json=envelope_json,
            status="pending",
            requested_at=now,
            expires_at=expires_at,
        )
        db.add(record)
        await db.commit()

        return self._to_dict(record)

    async def approve(
        self,
        db: AsyncSession,
        approval_id: str,
        decided_by: str,
        reason: str | None = None,
    ) -> dict | None:
        """Approve a pending approval.

        Returns the updated record dict, or None if not found.
        Raises ValueError if the approval is not in a state that allows approval.
        """
        record = await self._get_record(db, approval_id)
        if not record:
            return None

        if record.status != "pending":
            raise ValueError(
                f"Cannot approve: status is '{record.status}', expected 'pending'"
            )

        now = datetime.now(timezone.utc)
        expires = record.expires_at
        # Ensure both are tz-aware for comparison (SQLite returns naive datetimes)
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires and expires < now:
            # Auto-expire
            record.status = "expired"
            record.decided_at = now
            await db.commit()
            raise ValueError("Cannot approve: approval has expired")

        # Compute digest of approved envelope for later verification
        envelope_digest = hashlib.sha256(
            (record.envelope_json or "").encode()
        ).hexdigest()

        record.status = "approved"
        record.decided_at = now
        record.decided_by = decided_by
        record.decision_reason = reason
        record.approved_envelope_digest = envelope_digest
        await db.commit()

        return self._to_dict(record)

    async def deny(
        self,
        db: AsyncSession,
        approval_id: str,
        decided_by: str,
        reason: str | None = None,
    ) -> dict | None:
        """Deny a pending approval.

        Returns the updated record dict, or None if not found.
        Raises ValueError if the approval is not in a state that allows denial.
        """
        record = await self._get_record(db, approval_id)
        if not record:
            return None

        if record.status != "pending":
            raise ValueError(
                f"Cannot deny: status is '{record.status}', expected 'pending'"
            )

        now = datetime.now(timezone.utc)
        expires = record.expires_at
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires and expires < now:
            record.status = "expired"
            record.decided_at = now
            await db.commit()
            raise ValueError("Cannot deny: approval has expired")

        record.status = "denied"
        record.decided_at = now
        record.decided_by = decided_by
        record.decision_reason = reason
        await db.commit()

        return self._to_dict(record)

    async def get_approval(
        self, db: AsyncSession, approval_id: str
    ) -> dict | None:
        """Retrieve an approval record by ID."""
        record = await self._get_record(db, approval_id)
        if not record:
            return None
        return self._to_dict(record)

    @staticmethod
    def _is_expired(expires_at, now) -> bool:
        """Check if an expiry time is in the past, handling naive/aware datetimes."""
        if expires_at is None:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at < now

    async def list_pending(self, db: AsyncSession) -> list[dict]:
        """List all pending (non-expired) approvals."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Approval)
            .where(Approval.status == "pending")
            .order_by(Approval.requested_at)
        )
        records = result.scalars().all()
        # Filter expired in Python to handle naive/aware datetime comparison
        return [
            self._to_dict(r) for r in records
            if not self._is_expired(r.expires_at, now)
        ]

    async def check_expired(self, db: AsyncSession) -> int:
        """Mark expired pending approvals as expired. Returns count of newly expired."""
        now = datetime.now(timezone.utc)
        # Fetch all pending and check in Python for naive/aware compatibility
        result = await db.execute(
            select(Approval).where(Approval.status == "pending")
        )
        records = result.scalars().all()
        count = 0
        for r in records:
            if self._is_expired(r.expires_at, now):
                r.status = "expired"
                r.decided_at = now
                count += 1
        await db.commit()
        return count

    async def validate_approval(
        self, db: AsyncSession, approval_id: str, action_hash: str
    ) -> bool:
        """Validate that an approval exists, is approved, and matches the action hash."""
        record = await self._get_record(db, approval_id)
        if not record:
            return False
        if record.status != "approved":
            return False
        if record.action_hash != action_hash:
            return False
        # Check not expired
        now = datetime.now(timezone.utc)
        expires = record.expires_at
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires and expires < now:
            return False
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_record(
        self, db: AsyncSession, approval_id: str
    ) -> Approval | None:
        result = await db.execute(
            select(Approval).where(Approval.approval_id == approval_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_dict(record: Approval) -> dict:
        return {
            "approval_id": record.approval_id,
            "run_id": record.run_id,
            "action_hash": record.action_hash,
            "agent_id": record.requested_by_agent_id,
            "envelope_json": record.envelope_json,
            "status": record.status,
            "created_at": record.requested_at.isoformat() if record.requested_at else None,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "decided_at": record.decided_at.isoformat() if record.decided_at else None,
            "decided_by": record.decided_by,
            "decision_reason": record.decision_reason,
            "approved_envelope_digest": record.approved_envelope_digest,
        }
