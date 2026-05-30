from __future__ import annotations
"""Intent Service — classify user goals and create deterministic intent contracts."""

import json
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import hash_payload
from app.models.intent import Intent


# Deterministic intent classification rules
INTENT_RULES = [
    {
        "keywords": ["summarize", "email"],
        "allowed": ["email.read", "summarize", "respond_to_user"],
        "forbidden": ["email.send", "email.delete", "file.read_secret", "shell.execute_mock"],
        "approval_sensitive": ["external_write", "delete", "payment", "secret_access"],
        "risk_budget": "low",
    },
    {
        "keywords": ["send", "email"],
        "allowed": ["email.read", "email.send", "respond_to_user"],
        "forbidden": ["file.read_secret", "shell.execute_mock"],
        "approval_sensitive": ["external_write", "delete", "payment", "secret_access"],
        "risk_budget": "medium",
    },
    {
        "keywords": ["research", "web"],
        "allowed": ["web.read", "summarize", "respond_to_user"],
        "forbidden": ["email.send", "file.read_secret", "shell.execute_mock"],
        "approval_sensitive": ["external_write", "delete", "payment", "secret_access"],
        "risk_budget": "low",
    },
    {
        "keywords": ["access", "config"],
        "allowed": ["file.read", "file.read_secret", "email.send", "summarize", "respond_to_user"],
        "forbidden": ["shell.execute_mock"],
        "approval_sensitive": ["external_write", "delete", "payment", "secret_access"],
        "risk_budget": "medium",
    },
    {
        "keywords": ["read", "file"],
        "allowed": ["file.read", "summarize", "respond_to_user"],
        "forbidden": ["email.send", "file.read_secret", "shell.execute_mock"],
        "approval_sensitive": ["external_write", "delete", "payment", "secret_access"],
        "risk_budget": "low",
    },
    {
        "keywords": ["run", "command"],
        "allowed": ["shell.execute_mock", "respond_to_user"],
        "forbidden": [],
        "approval_sensitive": ["external_write", "delete", "payment", "secret_access", "shell"],
        "risk_budget": "high",
    },
]


def classify_intent(user_goal: str) -> dict:
    """Classify a user goal into allowed/forbidden actions. Deterministic for MVP."""
    goal_lower = user_goal.lower()

    for rule in INTENT_RULES:
        if all(re.search(r'\b' + re.escape(kw) + r's?\b', goal_lower) for kw in rule["keywords"]):
            return {
                "allowed_actions": rule["allowed"],
                "forbidden_actions": rule["forbidden"],
                "approval_required_for": rule["approval_sensitive"],
                "risk_budget": rule["risk_budget"],
            }

    # Default: minimal permissions
    return {
        "allowed_actions": ["respond_to_user"],
        "forbidden_actions": [
            "email.read", "email.send", "email.delete",
            "web.read", "file.read", "file.read_secret",
            "shell.execute_mock",
        ],
        "approval_required_for": ["external_write", "delete", "payment", "secret_access"],
        "risk_budget": "low",
    }


class IntentService:
    """Handles intent contract creation and retrieval."""

    async def create_intent(
        self,
        db: AsyncSession,
        user_goal: str,
        created_by: str = "system",
        resource_scope: dict | None = None,
    ) -> dict:
        """Create an intent contract from a user goal.

        `resource_scope` is the operator-authorized resource allowlist
        ({resource_type: [patterns]}). It is part of the intent contract and is
        folded into the intent hash so the authorized scope is tamper-evident.
        """
        classification = classify_intent(user_goal)
        resource_scope = resource_scope or {}

        # Generate hash from canonical form (include created_by for ownership isolation)
        hash_input = {
            "user_goal": user_goal,
            "allowed_actions": sorted(classification["allowed_actions"]),
            "forbidden_actions": sorted(classification["forbidden_actions"]),
            "resource_scope": json.dumps(resource_scope, sort_keys=True),
            "risk_budget": classification["risk_budget"],
            "created_by": created_by,
        }
        intent_hash = hash_payload(hash_input)

        # Upsert: return existing if hash already exists
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

        # Store in DB
        intent = Intent(
            intent_id=intent_id,
            user_goal=user_goal,
            allowed_actions_json=json.dumps(classification["allowed_actions"]),
            forbidden_actions_json=json.dumps(classification["forbidden_actions"]),
            resource_scope_json=json.dumps(resource_scope),
            approval_required_for_json=json.dumps(classification["approval_required_for"]),
            risk_budget=classification["risk_budget"],
            intent_hash=intent_hash,
            created_by=created_by,
        )
        db.add(intent)
        await db.commit()

        return {
            "intent_id": intent_id,
            "user_goal": user_goal,
            "allowed_actions": classification["allowed_actions"],
            "forbidden_actions": classification["forbidden_actions"],
            "resource_scope": resource_scope,
            "risk_budget": classification["risk_budget"],
            "approval_required_for": classification["approval_required_for"],
            "intent_hash": intent_hash,
            "created_at": now,
            "created_by": created_by,
        }

    async def get_intent(self, db: AsyncSession, intent_id: str) -> dict | None:
        """Fetch an intent contract by ID."""
        result = await db.execute(select(Intent).where(Intent.intent_id == intent_id))
        intent = result.scalar_one_or_none()
        if not intent:
            return None

        return {
            "intent_id": intent.intent_id,
            "user_goal": intent.user_goal,
            "allowed_actions": json.loads(intent.allowed_actions_json),
            "forbidden_actions": json.loads(intent.forbidden_actions_json),
            "resource_scope": json.loads(intent.resource_scope_json or "{}"),
            "approval_required_for": json.loads(intent.approval_required_for_json),
            "risk_budget": intent.risk_budget,
            "intent_hash": intent.intent_hash,
            "created_at": intent.created_at,
            "created_by": intent.created_by,
        }

    async def get_intent_by_hash(self, db: AsyncSession, intent_hash: str) -> dict | None:
        """Fetch an intent contract by hash."""
        result = await db.execute(select(Intent).where(Intent.intent_hash == intent_hash))
        intent = result.scalars().first()  # Use .first() not scalar_one_or_none() for safety
        if not intent:
            return None

        return {
            "intent_id": intent.intent_id,
            "user_goal": intent.user_goal,
            "allowed_actions": json.loads(intent.allowed_actions_json),
            "forbidden_actions": json.loads(intent.forbidden_actions_json),
            "resource_scope": json.loads(intent.resource_scope_json or "{}"),
            "approval_required_for": json.loads(intent.approval_required_for_json),
            "risk_budget": intent.risk_budget,
            "intent_hash": intent.intent_hash,
            "created_at": intent.created_at,
            "created_by": intent.created_by,
        }
