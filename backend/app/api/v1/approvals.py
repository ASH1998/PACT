"""V1 Approvals API — approve or deny pending actions via ApprovalService."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.approval import ApprovalService

router = APIRouter()


def _get_approval_service():
    return ApprovalService()


@router.get("")
async def list_approvals(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """List approvals. Optionally filter by status."""
    svc = _get_approval_service()
    if status == "pending" or status is None:
        pending = await svc.list_pending(db)
        return {"approvals": pending, "count": len(pending)}
    # For other statuses, query DB directly
    from app.models.approval import Approval

    query = select(Approval)
    if status:
        query = query.where(Approval.status == status)
    result = await db.execute(query)
    approvals = result.scalars().all()
    return {
        "approvals": [
            {
                "approval_id": a.approval_id,
                "run_id": a.run_id,
                "action_hash": a.action_hash,
                "requested_by_agent_id": a.requested_by_agent_id,
                "status": a.status,
                "requested_at": a.requested_at.isoformat() if a.requested_at else None,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                "decided_at": a.decided_at.isoformat() if a.decided_at else None,
                "decided_by": a.decided_by,
                "decision_reason": a.decision_reason,
            }
            for a in approvals
        ],
        "count": len(approvals),
    }


@router.post("/{approval_id}/approve")
async def approve_action(
    approval_id: str,
    decided_by: str = "api_user",
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending action by real approval_id."""
    svc = _get_approval_service()
    try:
        result = await svc.approve(
            db, approval_id, decided_by=decided_by, reason=reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Approval {approval_id} not found"
        )
    return result


@router.post("/{approval_id}/deny")
async def deny_action(
    approval_id: str,
    decided_by: str = "api_user",
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Deny a pending action by real approval_id."""
    svc = _get_approval_service()
    try:
        result = await svc.deny(
            db, approval_id, decided_by=decided_by, reason=reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Approval {approval_id} not found"
        )
    return result


@router.get("/{approval_id}")
async def get_approval(approval_id: str, db: AsyncSession = Depends(get_db)):
    """Get approval details."""
    svc = _get_approval_service()
    result = await svc.get_approval(db, approval_id)
    if not result:
        raise HTTPException(
            status_code=404, detail=f"Approval {approval_id} not found"
        )
    return result
