"""Configurable policy service — uses PolicyConfig rules AND tool registry metadata.

This is the production policy evaluator. Unlike the legacy PolicyService which
uses hardcoded Python if/elif chains and trusts caller-declared provenance,
this service:
  1. Looks up the tool in the registry for authoritative metadata.
  2. Blocks unknown/unregistered tools.
  3. Uses the registry's side_effect, not the caller's provenance.
  4. Checks default_requires_approval from tool metadata.
  5. Evaluates structured PolicyConfig rules against this enriched context.
"""

from __future__ import annotations

from typing import Optional

from app.core.policy_config import PolicyConfig
from app.core.registry import ToolRegistry, get_default_registry
from app.schemas import Decision, Severity, PolicyDecision
from app.services.policy import PolicyService


class ConfigurablePolicyService(PolicyService):
    """Production policy service backed by PolicyConfig rules and tool registry.

    Inherits from PolicyService for type compatibility with GatewayService.
    """

    def __init__(
        self,
        config: Optional[PolicyConfig] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.config = config or PolicyConfig()
        self._tool_registry = tool_registry  # lazy-loaded if None

    @property
    def tool_registry(self) -> ToolRegistry:
        if self._tool_registry is None:
            self._tool_registry = get_default_registry()
        return self._tool_registry

    def evaluate(
        self,
        tool: str,
        allowed_actions: list[str],
        forbidden_actions: list[str],
        provenance: dict,
        passport_valid: bool = True,
        passport_reason: str = "Valid",
        signature_valid: bool = True,
        capability_valid: bool = True,
        capability_reason: str = "Valid",
        resource: str = "",
        resource_in_scope: bool = True,
    ) -> PolicyDecision:
        """Evaluate using configurable rules + tool registry metadata."""
        influenced_by = provenance.get("influenced_by", [])
        uses_data = provenance.get("uses_data", [])

        # --- Look up authoritative tool metadata from registry ---
        tool_entry = self.tool_registry.get_tool(tool)
        tool_known = tool_entry is not None

        if tool_known:
            tool_meta = tool_entry["metadata"]
            # Authoritative side_effect from registry, not from caller's provenance
            registry_side_effect = tool_meta.get("side_effect", "none")
            registry_sensitivity = tool_meta.get("sensitivity", "low")
            registry_requires_approval = tool_meta.get("default_requires_approval", False)
        else:
            registry_side_effect = "unknown"
            registry_sensitivity = "unknown"
            registry_requires_approval = False

        # Build evaluation context — uses REGISTRY metadata, not caller-declared
        context = {
            "tool": tool,
            "allowed_actions": allowed_actions,
            "forbidden_actions": forbidden_actions,
            "influenced_by": influenced_by,
            "uses_data": uses_data,
            # Use registry side_effect as authoritative; fall back to provenance for legacy
            "side_effect": registry_side_effect if tool_known else provenance.get("side_effect"),
            "passport_valid": passport_valid,
            "passport_reason": passport_reason,
            "signature_valid": signature_valid,
            "capability_valid": capability_valid,
            "capability_reason": capability_reason,
            "tool_not_in_allowed": tool not in allowed_actions,
            "tool_in_forbidden": tool in forbidden_actions,
            "has_secret_data": "secret" in uses_data or "secret" in influenced_by,
            "tool_unknown": not tool_known,
            # Additional registry-derived context
            "sensitivity": registry_sensitivity,
            "default_requires_approval": registry_requires_approval,
            # Resource authority: the requested resource and whether it is within
            # the operator-authorized scope on the intent contract.
            "resource": resource,
            "resource_in_scope": resource_in_scope,
        }

        reasons = []
        matched_action = None
        max_risk = 0
        severity_str = "low"

        for rule in self.config.rules:
            result = self.config.evaluate_rule(rule, context)
            if result is not None:
                reasons.append(result["reason"])
                if result["action"] in ("BLOCK", "REQUIRE_APPROVAL"):
                    matched_action = result["action"]
                    max_risk = max(max_risk, result.get("risk_score", 50))
                    severity_str = result.get("severity", severity_str)
                    break
                else:
                    max_risk = max(max_risk, result.get("risk_score", 0))

        # Also check registry's default_requires_approval
        if matched_action is None and registry_requires_approval and tool_known:
            matched_action = "REQUIRE_APPROVAL"
            reasons.append(f"Tool '{tool}' requires approval per registry metadata")
            max_risk = max(max_risk, 50)
            severity_str = "high"

        if not reasons:
            reasons.append("Action is valid and aligned with intent")

        if matched_action == "BLOCK":
            decision = Decision.BLOCK
        elif matched_action == "REQUIRE_APPROVAL":
            decision = Decision.REQUIRE_APPROVAL
        else:
            decision = Decision.ALLOW

        return PolicyDecision(
            decision=decision,
            risk_score=max_risk,
            severity=(
                Severity(severity_str)
                if severity_str in [s.value for s in Severity]
                else Severity.LOW
            ),
            reasons=reasons,
        )
