from __future__ import annotations
"""Capability Service — issue, validate, and consume short-lived capability tokens."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import sign, verify, canonical_json, hash_payload
from app.models.capability import CapabilityToken as CapabilityTokenModel


class CapabilityService:
    """Handles capability token lifecycle."""

    def __init__(self, issuer_private_key: str, issuer_public_key: str):
        self.issuer_private_key = issuer_private_key
        self.issuer_public_key = issuer_public_key

    async def issue_token(
        self,
        db: AsyncSession,
        agent_id: str,
        intent_hash: str,
        capability: str,
        resource: str = "default",
        max_uses: int = 5,
        ttl_seconds: int = 300,
    ) -> dict:
        """Issue a signed capability token."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        token_data = {
            "token_type": "PACT-CAP",
            "agent_id": agent_id,
            "intent_hash": intent_hash,
            "capability": capability,
            "resource": resource,
            "max_uses": max_uses,
            "uses_remaining": max_uses,
            "expires_at": expires_at.isoformat(),
        }

        # Generate token hash (exclude token_hash and signature)
        token_hash = hash_payload(token_data)
        token_data["token_hash"] = token_hash

        # Sign — only immutable fields so signature stays valid after consume_use()
        signing_payload = {
            "token_type": "PACT-CAP",
            "token_hash": token_hash,
            "agent_id": agent_id,
            "intent_hash": intent_hash,
            "capability": capability,
            "resource": resource,
            "max_uses": max_uses,
            "expires_at": expires_at.isoformat(),
        }
        payload = canonical_json(signing_payload)
        signature = sign(self.issuer_private_key, payload)
        token_data["signature"] = signature

        # Store in DB
        token = CapabilityTokenModel(
            token_hash=token_hash,
            agent_id=agent_id,
            intent_hash=intent_hash,
            capability=capability,
            resource=resource,
            max_uses=max_uses,
            uses_remaining=max_uses,
            expires_at=expires_at,
            status="active",
            signature=signature,
        )
        db.add(token)
        await db.commit()

        return token_data

    async def validate_token(
        self,
        db: AsyncSession,
        token_hash: str,
        agent_id: str,
        intent_hash: str,
        capability: str,
        resource: str | None = None,
    ) -> tuple[bool, str]:
        """Validate a capability token. Returns (valid, reason)."""
        result = await db.execute(
            select(CapabilityTokenModel).where(CapabilityTokenModel.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()

        if not token:
            return False, "Token not found"

        if token.status != "active":
            return False, f"Token status is {token.status}"

        if token.agent_id != agent_id:
            return False, "Token issued to different agent"

        if token.intent_hash != intent_hash:
            return False, "Token bound to different intent"

        if token.capability != capability:
            return False, f"Token grants {token.capability}, not {capability}"

        # Resource binding check
        if resource is not None and token.resource != resource:
            return False, f"Token bound to resource {token.resource}, not {resource}"

        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            return False, "Token expired"

        if token.uses_remaining <= 0:
            return False, "Token use count exhausted"

        # Verify token signature
        # Normalize expires_at to match the original signed format (always UTC with +00:00)
        exp = token.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        # Only immutable fields are covered by the signature
        token_payload = {
            "token_type": "PACT-CAP",
            "token_hash": token.token_hash,
            "agent_id": token.agent_id,
            "intent_hash": token.intent_hash,
            "capability": token.capability,
            "resource": token.resource,
            "max_uses": token.max_uses,
            "expires_at": exp.isoformat(),
        }
        payload_bytes = canonical_json(token_payload)
        if not verify(self.issuer_public_key, payload_bytes, token.signature):
            return False, "Token signature invalid"

        return True, "Valid"

    async def consume_use(self, db: AsyncSession, token_hash: str) -> bool:
        """Decrement uses_remaining. Returns False if already exhausted."""
        result = await db.execute(
            select(CapabilityTokenModel).where(CapabilityTokenModel.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()

        if not token or token.uses_remaining <= 0:
            return False

        token.uses_remaining -= 1
        if token.uses_remaining <= 0:
            token.status = "exhausted"
        await db.commit()
        return True

    async def get_token(self, db: AsyncSession, token_hash: str) -> dict | None:
        """Fetch a token by hash."""
        result = await db.execute(
            select(CapabilityTokenModel).where(CapabilityTokenModel.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()
        if not token:
            return None

        return {
            "token_type": "PACT-CAP",
            "token_hash": token.token_hash,
            "agent_id": token.agent_id,
            "intent_hash": token.intent_hash,
            "capability": token.capability,
            "resource": token.resource,
            "max_uses": token.max_uses,
            "uses_remaining": token.uses_remaining,
            "expires_at": token.expires_at.isoformat(),
            "status": token.status,
            "signature": token.signature,
        }
