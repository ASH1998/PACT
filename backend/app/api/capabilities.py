"""Capability API routes — issue and validate capability tokens."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import CapabilityIssueRequest, CapabilityValidateRequest, CapabilityResponse
from app.services.capability import CapabilityService
from app.crypto import generate_keypair

router = APIRouter()

# Module-level singleton issuer keypair — reused across all requests
_ISSUER_PRIVATE, _ISSUER_PUBLIC = generate_keypair()


def _get_capability_service() -> CapabilityService:
    """Create a capability service with a stable demo issuer keypair."""
    return CapabilityService(_ISSUER_PRIVATE, _ISSUER_PUBLIC)


@router.post("/issue", response_model=CapabilityResponse)
async def issue_token(
    req: CapabilityIssueRequest,
    db: AsyncSession = Depends(get_db),
):
    """Issue a new capability token."""
    svc = _get_capability_service()
    result = await svc.issue_token(
        db=db,
        agent_id=req.agent_id,
        intent_hash=req.intent_hash,
        capability=req.capability,
        resource=req.resource,
        max_uses=req.max_uses,
        ttl_seconds=req.ttl_seconds,
    )
    return CapabilityResponse(
        token_hash=result["token_hash"],
        agent_id=result["agent_id"],
        intent_hash=result["intent_hash"],
        capability=result["capability"],
        resource=result["resource"],
        max_uses=result["max_uses"],
        uses_remaining=result["uses_remaining"],
        expires_at=result["expires_at"],
        status="active",
    )


@router.post("/validate")
async def validate_token(
    req: CapabilityValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate a capability token."""
    svc = _get_capability_service()
    valid, reason = await svc.validate_token(
        db=db,
        token_hash=req.token_hash,
        agent_id=req.agent_id,
        intent_hash=req.intent_hash,
        capability=req.capability,
    )
    return {"valid": valid, "reason": reason}
