from __future__ import annotations
"""Passport Service — create, sign, store, and verify agent passports."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import generate_keypair, sign, verify, canonical_json
from app.models.agent import Agent


class PassportService:
    """Handles agent passport lifecycle."""

    def __init__(self, issuer_private_key: str, issuer_public_key: str):
        self.issuer_private_key = issuer_private_key
        self.issuer_public_key = issuer_public_key

    async def create_passport(
        self,
        db: AsyncSession,
        agent_id: str,
        owner: str,
        agent_type: str,
        allowed_domains: list[str],
        risk_tier: str = "medium",
        ttl_days: int = 30,
    ) -> dict:
        """Create a new agent passport with Ed25519 keypair."""
        agent_private_key, agent_public_key = generate_keypair()

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=ttl_days)

        # Build passport (without signature)
        passport_data = {
            "agent_id": agent_id,
            "owner": owner,
            "agent_type": agent_type,
            "public_key": agent_public_key,
            "allowed_domains": allowed_domains,
            "risk_tier": risk_tier,
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        # Sign with issuer key
        payload = canonical_json(passport_data)
        issuer_signature = sign(self.issuer_private_key, payload)
        passport_data["issuer_signature"] = issuer_signature

        # Store in DB
        agent = Agent(
            agent_id=agent_id,
            owner=owner,
            agent_type=agent_type,
            public_key=agent_public_key,
            passport_json=json.dumps(passport_data),
            allowed_domains_json=json.dumps(allowed_domains),
            risk_tier=risk_tier,
            status="active",
            expires_at=expires_at,
        )
        db.add(agent)
        await db.commit()

        return {
            "passport": passport_data,
            "agent_private_key": agent_private_key,  # Return once; caller must store it
        }

    async def get_passport(self, db: AsyncSession, agent_id: str) -> dict | None:
        """Fetch a stored passport."""
        result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
        agent = result.scalar_one_or_none()
        if not agent:
            return None
        return json.loads(agent.passport_json)

    async def verify_passport(self, passport: dict) -> tuple[bool, str]:
        """Verify passport expiry and issuer signature."""
        # Check expiry
        expires_at = datetime.fromisoformat(passport["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            return False, "Passport expired"

        # Verify issuer signature
        passport_copy = {k: v for k, v in passport.items()}
        sig = passport_copy.pop("issuer_signature")
        payload = canonical_json(passport_copy)
        valid = verify(self.issuer_public_key, payload, sig)

        if not valid:
            return False, "Invalid issuer signature"

        return True, "Valid"

    async def verify_action_signature(
        self, db: AsyncSession, agent_id: str, payload: bytes, signature: str
    ) -> bool:
        """Verify an action signature using the agent's stored public key."""
        result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
        agent = result.scalar_one_or_none()
        if not agent:
            return False
        return verify(agent.public_key, payload, signature)
