"""Policy persistence helpers and runtime reload support."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.factory import get_runtime
from app.core.policy_config import DEFAULT_POLICY_RULES, PolicyConfig
from app.models.policy import Policy as PolicyModel
from app.services.configurable_policy import ConfigurablePolicyService

RUNTIME_ACTIONS = frozenset({"ALLOW", "BLOCK", "REQUIRE_APPROVAL"})


def encode_rules(rules: list[dict[str, Any]]) -> str:
    """Encode policy rules for DB storage."""
    return json.dumps(rules)


def decode_rules(policy: PolicyModel) -> list[dict[str, Any]]:
    """Decode stored policy rules, treating malformed legacy rows as empty."""
    try:
        rules = json.loads(policy.rules_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(rules, list):
        return []
    return [rule for rule in rules if isinstance(rule, dict)]


def policy_to_response(policy: PolicyModel) -> dict[str, Any]:
    """Return the stable v1 policy response shape."""
    return {
        "policy_id": policy.policy_id,
        "name": policy.name,
        "description": policy.description,
        "rules": decode_rules(policy),
        "enabled": policy.enabled,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
    }


def is_runtime_rule(rule: dict[str, Any]) -> bool:
    """Return True for rules the current evaluator can safely enforce."""
    action = rule.get("action")
    condition = rule.get("condition")
    return (
        isinstance(condition, dict)
        and isinstance(action, str)
        and action in RUNTIME_ACTIONS
    )


async def load_active_runtime_rules(db: AsyncSession) -> list[dict[str, Any]]:
    """Load enabled structured rules for runtime evaluation."""
    result = await db.execute(
        select(PolicyModel)
        .where(PolicyModel.enabled.is_(True))
        .order_by(PolicyModel.id)
    )
    runtime_rules: list[dict[str, Any]] = []
    for policy in result.scalars().all():
        runtime_rules.extend(rule for rule in decode_rules(policy) if is_runtime_rule(rule))
    return [*DEFAULT_POLICY_RULES, *runtime_rules]


async def reload_runtime_policy(db: AsyncSession) -> int:
    """Apply active persisted policies to the process runtime.

    Loose policy documents are still persisted and returned by the API. Only
    structured rules with `condition` and `action` are loaded into enforcement,
    and they are additive to the built-in safety baseline.
    """
    runtime = get_runtime()
    if not isinstance(runtime.policy_service, ConfigurablePolicyService):
        return 0

    rules = await load_active_runtime_rules(db)
    runtime.policy_service.config = PolicyConfig(rules=rules)
    return len(rules)
