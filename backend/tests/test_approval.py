"""Tests for ApprovalService and ApprovalGatewayService."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import update

from app.models.approval import Approval
from app.services.approval import ApprovalService
from app.services.approval_gateway import ApprovalGatewayService
from app.schemas import Decision, Severity


# ──────────────────────────────────────────────────────────────────────
# ApprovalService
# ──────────────────────────────────────────────────────────────────────


class TestApprovalService:
    """Tests for the ApprovalService."""

    @pytest.fixture
    def svc(self):
        return ApprovalService()

    async def test_create_approval(self, svc, setup_db):
        """create_approval inserts a pending record."""
        from app.database import async_session

        async with async_session() as db:
            record = await svc.create_approval(
                db=db,
                run_id="run_1",
                action_hash="ah_1",
                agent_id="agent_1",
                envelope_json=json.dumps({"tool": "test"}),
                ttl_seconds=600,
            )

        assert record["status"] == "pending"
        assert record["run_id"] == "run_1"
        assert record["action_hash"] == "ah_1"
        assert record["agent_id"] == "agent_1"
        assert record["approval_id"].startswith("appr_")

    async def test_approve_changes_status(self, svc, setup_db):
        """approve() changes status to approved and sets decided_by."""
        from app.database import async_session

        async with async_session() as db:
            created = await svc.create_approval(
                db=db,
                run_id="run_2",
                action_hash="ah_2",
                agent_id="agent_2",
                envelope_json="{}",
                ttl_seconds=3600,
            )

            approved = await svc.approve(
                db=db,
                approval_id=created["approval_id"],
                decided_by="human_admin",
                reason="Looks safe",
            )

        assert approved["status"] == "approved"
        assert approved["decided_by"] == "human_admin"
        assert approved["decision_reason"] == "Looks safe"
        assert approved["approved_envelope_digest"] is not None

    async def test_deny_changes_status(self, svc, setup_db):
        """deny() changes status to denied."""
        from app.database import async_session

        async with async_session() as db:
            created = await svc.create_approval(
                db=db,
                run_id="run_3",
                action_hash="ah_3",
                agent_id="agent_3",
                envelope_json="{}",
                ttl_seconds=3600,
            )

            denied = await svc.deny(
                db=db,
                approval_id=created["approval_id"],
                decided_by="human_admin",
                reason="Too risky",
            )

        assert denied["status"] == "denied"
        assert denied["decided_by"] == "human_admin"
        assert denied["decision_reason"] == "Too risky"

    async def test_approve_expired_fails(self, svc, setup_db):
        """Approving an expired approval raises ValueError."""
        from app.database import async_session

        async with async_session() as db:
            created = await svc.create_approval(
                db=db,
                run_id="run_4",
                action_hash="ah_4",
                agent_id="agent_4",
                envelope_json="{}",
                ttl_seconds=1,
            )

            # Force-expire the record
            await db.execute(
                update(Approval)
                .where(Approval.approval_id == created["approval_id"])
                .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=10))
            )
            await db.commit()

            with pytest.raises(ValueError, match="expired"):
                await svc.approve(
                    db=db,
                    approval_id=created["approval_id"],
                    decided_by="admin",
                )

    async def test_double_approve_fails(self, svc, setup_db):
        """Approving an already-approved record raises ValueError."""
        from app.database import async_session

        async with async_session() as db:
            created = await svc.create_approval(
                db=db,
                run_id="run_5",
                action_hash="ah_5",
                agent_id="agent_5",
                envelope_json="{}",
            )

            await svc.approve(db=db, approval_id=created["approval_id"], decided_by="admin")

            with pytest.raises(ValueError, match="status is 'approved'"):
                await svc.approve(db=db, approval_id=created["approval_id"], decided_by="admin2")

    async def test_list_pending(self, svc, setup_db):
        """list_pending returns only pending, non-expired approvals."""
        from app.database import async_session

        async with async_session() as db:
            p1 = await svc.create_approval(
                db=db, run_id="r", action_hash="h1", agent_id="a", envelope_json="{}", ttl_seconds=3600,
            )
            p2 = await svc.create_approval(
                db=db, run_id="r", action_hash="h2", agent_id="a", envelope_json="{}", ttl_seconds=3600,
            )
            # Approve one
            await svc.approve(db=db, approval_id=p2["approval_id"], decided_by="admin")

            pending = await svc.list_pending(db)

        ids = [p["approval_id"] for p in pending]
        assert p1["approval_id"] in ids
        assert p2["approval_id"] not in ids

    async def test_check_expired(self, svc, setup_db):
        """check_expired marks old pending approvals as expired."""
        from app.database import async_session

        async with async_session() as db:
            created = await svc.create_approval(
                db=db, run_id="r", action_hash="h", agent_id="a", envelope_json="{}", ttl_seconds=5,
            )

            # Force-expire
            await db.execute(
                update(Approval)
                .where(Approval.approval_id == created["approval_id"])
                .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
            )
            await db.commit()

            count = await svc.check_expired(db)
            assert count == 1

            # Verify status changed
            record = await svc.get_approval(db, created["approval_id"])
            assert record["status"] == "expired"

    async def test_validate_approval(self, svc, setup_db):
        """validate_approval returns True only for approved, matching records."""
        from app.database import async_session

        async with async_session() as db:
            created = await svc.create_approval(
                db=db, run_id="r", action_hash="ah_match", agent_id="a", envelope_json="{}", ttl_seconds=3600,
            )

            # Not yet approved
            assert await svc.validate_approval(db, created["approval_id"], "ah_match") is False

            # Approve
            await svc.approve(db=db, approval_id=created["approval_id"], decided_by="admin")
            assert await svc.validate_approval(db, created["approval_id"], "ah_match") is True

            # Wrong action hash
            assert await svc.validate_approval(db, created["approval_id"], "ah_other") is False

    async def test_get_approval_not_found(self, svc, setup_db):
        """get_approval returns None for unknown IDs."""
        from app.database import async_session

        async with async_session() as db:
            result = await svc.get_approval(db, "appr_nonexistent")
        assert result is None


# ──────────────────────────────────────────────────────────────────────
# ApprovalGatewayService
# ──────────────────────────────────────────────────────────────────────


class TestApprovalGatewayService:
    """Tests for ApprovalGatewayService."""

    async def test_require_approval_creates_record(self, setup_db):
        """When gateway returns REQUIRE_APPROVAL, an approval record is created."""
        from app.database import async_session

        # Mock gateway that returns REQUIRE_APPROVAL
        mock_gateway = AsyncMock()
        mock_gateway.execute.return_value = MagicMock(
            decision=Decision.REQUIRE_APPROVAL,
            action_hash="action_h",
            run_id="run_x",
            reasons=["Shell needs approval"],
            risk_score=40,
            severity=Severity.MEDIUM,
            tool_result=None,
        )

        approval_svc = ApprovalService()
        gw = ApprovalGatewayService(gateway=mock_gateway, approval_service=approval_svc)

        async with async_session() as db:
            result = await gw.execute_with_approval(
                db=db,
                envelope={"agent_id": "a1", "tool": "shell.run_mock", "args": {}},
                run_id="run_x",
            )

        assert result["decision"] == "REQUIRE_APPROVAL"
        assert "approval_id" in result
        assert result["action_hash"] == "action_h"

    async def test_allow_passes_through(self, setup_db):
        """When gateway returns ALLOW, the result passes through unchanged."""
        from app.database import async_session

        mock_gateway = AsyncMock()
        mock_gateway.execute.return_value = MagicMock(
            decision=Decision.ALLOW,
            action_hash="action_h2",
            run_id="run_y",
            reasons=["All good"],
            risk_score=10,
            severity=Severity.LOW,
            tool_result={"output": "done"},
        )

        approval_svc = ApprovalService()
        gw = ApprovalGatewayService(gateway=mock_gateway, approval_service=approval_svc)

        async with async_session() as db:
            result = await gw.execute_with_approval(
                db=db,
                envelope={"agent_id": "a1", "tool": "db.read", "args": {}},
                run_id="run_y",
            )

        assert result["decision"] == "ALLOW"
        assert result["tool_result"] == {"output": "done"}
        assert "approval_id" not in result

    async def test_resume_approved(self, setup_db):
        """resume_approved re-executes the envelope through the gateway."""
        from app.database import async_session

        mock_gateway = AsyncMock()
        # First call: REQUIRE_APPROVAL
        # Second call (resume): ALLOW
        mock_gateway.execute.side_effect = [
            MagicMock(
                decision=Decision.REQUIRE_APPROVAL,
                action_hash="ah_resume",
                run_id="run_resume",
                reasons=["Needs approval"],
                risk_score=40,
                severity=Severity.MEDIUM,
                tool_result=None,
            ),
            MagicMock(
                decision=Decision.ALLOW,
                action_hash="ah_resume",
                run_id="run_resume",
                reasons=["Approved"],
                risk_score=10,
                severity=Severity.LOW,
                tool_result={"output": "done"},
            ),
        ]

        approval_svc = ApprovalService()
        gw = ApprovalGatewayService(gateway=mock_gateway, approval_service=approval_svc)

        async with async_session() as db:
            # First call creates the approval
            envelope = {"agent_id": "a1", "tool": "t", "args": {"x": 1}}
            result = await gw.execute_with_approval(db, envelope, "run_resume")
            appr_id = result["approval_id"]

            # Approve it
            await approval_svc.approve(db, appr_id, decided_by="admin")

            # Resume
            resume_result = await gw.resume_approved(db, appr_id, decided_by="admin")

        assert resume_result["decision"] == "ALLOW"
        assert resume_result["approval_id"] == appr_id

    async def test_resume_not_approved_fails(self, setup_db):
        """resume_approved fails if approval is still pending."""
        from app.database import async_session

        mock_gateway = AsyncMock()
        mock_gateway.execute.return_value = MagicMock(
            decision=Decision.REQUIRE_APPROVAL,
            action_hash="ah",
            run_id="r",
            reasons=["Need approval"],
            risk_score=40,
            severity=Severity.MEDIUM,
            tool_result=None,
        )

        approval_svc = ApprovalService()
        gw = ApprovalGatewayService(gateway=mock_gateway, approval_service=approval_svc)

        async with async_session() as db:
            result = await gw.execute_with_approval(
                db, {"agent_id": "a", "tool": "t", "args": {}}, "r"
            )
            appr_id = result["approval_id"]

            resume_result = await gw.resume_approved(db, appr_id, "admin")

        assert "error" in resume_result
        assert "not approved" in resume_result["error"]
