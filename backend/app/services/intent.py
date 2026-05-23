from __future__ import annotations
"""Intent Service — classify user goals and create deterministic intent contracts."""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import canonical_json, hash_payload
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
        "keywords": ["read", "file"],
        "allowed": ["file.read", "summarize", "respond_to_user"],
        "forbidden": ["email.send", "file.read_secret", "shell.execute_mock"],
        "approval_sensitive": ["external_write", "delete", "payment", "secret_access"],
        "risk_budget": "low",
    },
]


def classify_intent(user_goal: str) -> dict:
    """Classify a user goal into allowed/forbidden actions. Deterministic for MVP."""
    goal_lower = user_goal.lower()

    for rule in INTENT_RULES:
        if all(kw in goal_lower for kw in rule["keywords"]):
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

    async def create_intent(self, db: AsyncSession, user_goal: str) -> dict:
        """Create an intent contract from a user goal."""
        classification = classify_intent(user_goal)
        intent_id = f"intent_{uuid.uuid4().hex[:12]}"

        intent_data = {
            "intent_id": intent_id,
            "user_goal": user_goal,
            "allowed_actions": classification["allowed_actions"],
            "forbidden_actions": classification["forbidden_actions"],
            "risk_budget": classification["risk_budget"],
            "approval_required_for": classification["approval_required_for"],
        }

        # Generate hash from canonical form (exclude intent_id and intent_hash)
        hash_input = {
            "user_goal": user_goal,
            "allowed_actions": sorted(classification["allowed_actions"]),
            "forbidden_actions": sorted(classification["forbidden_actions"]),
            "risk_budget": classification["risk_budget"],
        }
        intent_hash = hash_payload(hash_input)
        intent_data["intent_hash"] = intent_hash

        # Store in DB
        intent = Intent(
            intent_id=intent_id,
            user_goal=user_goal,
            allowed_actions_json=json.dumps(classification["allowed_actions"]),
            forbidden_actions_json=json.dumps(classification["forbidden_actions"]),
            approval_required_for_json=json.dumps(classification["approval_required_for"]),
            risk_budget=classification["risk_budget"],
            intent_hash=intent_hash,
        )
        db.add(intent)
        await db.commit()

        return intent_data

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
            "approval_required_for": json.loads(intent.approval_required_for_json),
            "risk_budget": intent.risk_budget,
            "intent_hash": intent.intent_hash,
        }

    async def get_intent_by_hash(self, db: AsyncSession, intent_hash: str) -> dict | None:
        """Fetch an intent contract by hash."""
        result = await db.execute(select(Intent).where(Intent.intent_hash == intent_hash))
        intent = result.scalar_one_or_none()
        if not intent:
            return None

        return {
            "intent_id": intent.intent_id,
            "user_goal": intent.user_goal,
            "allowed_actions": json.loads(intent.allowed_actions_json),
            "forbidden_actions": json.loads(intent.forbidden_actions_json),
            "approval_required_for": json.loads(intent.approval_required_for_json),
            "risk_budget": intent.risk_budget,
            "intent_hash": intent.intent_hash,
        }
