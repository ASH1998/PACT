"""Policy configuration loader for PACT.

Loads policy rules from a dict/YAML structure instead of hardcoded Python.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml


# Default policy rules — matches current hardcoded behavior
DEFAULT_POLICY_RULES = [
    {
        "id": "R1-invalid-passport",
        "name": "Invalid Passport",
        "condition": {"passport_valid": False},
        "action": "BLOCK",
        "severity": "critical",
        "risk_score": 100,
        "reason": "Invalid agent passport: {passport_reason}",
    },
    {
        "id": "R2-invalid-signature",
        "name": "Invalid Signature",
        "condition": {"signature_valid": False},
        "action": "BLOCK",
        "severity": "critical",
        "risk_score": 100,
        "reason": "Invalid action signature",
    },
    {
        "id": "R3-invalid-capability",
        "name": "Invalid Capability",
        "condition": {"capability_valid": False},
        "action": "BLOCK",
        "severity": "high",
        "risk_score": 60,
        "reason": "Capability token invalid: {capability_reason}",
    },
    {
        "id": "R4-intent-mismatch",
        "name": "Intent Mismatch",
        "condition": {"tool_not_in_allowed": True},
        "action": "BLOCK",
        "severity": "high",
        "risk_score": 50,
        "reason": "{tool} not allowed by intent contract",
    },
    {
        "id": "R5-intent-forbidden",
        "name": "Intent Forbidden",
        "condition": {"tool_in_forbidden": True},
        "action": "BLOCK",
        "severity": "high",
        "risk_score": 50,
        "reason": "{tool} is explicitly forbidden by intent contract",
    },
    # Hard authorization boundary — evaluated before approval/taint rules so an
    # unauthorized resource is blocked outright, never merely approvable. Risk is
    # graduated by the danger of the out-of-scope target: an external write (e.g.
    # mailing an unauthorized recipient) or shell/web reach is far more dangerous
    # than reading a local file outside the path allowlist. Ordered most-specific
    # first because the evaluator stops at the first matching BLOCK rule.
    {
        "id": "R12a-scope-external-write",
        "name": "Out-Of-Scope External Write",
        "condition": {"resource_in_scope": False, "side_effect": "external_write"},
        "action": "BLOCK",
        "severity": "critical",
        "risk_score": 85,
        "reason": "External write to '{resource}' is outside the authorized scope for {tool}",
    },
    {
        "id": "R12b-scope-shell",
        "name": "Out-Of-Scope Shell Command",
        "condition": {"resource_in_scope": False, "tool_prefix": "shell."},
        "action": "BLOCK",
        "severity": "high",
        "risk_score": 80,
        "reason": "Shell command '{resource}' is outside the authorized scope for {tool}",
    },
    {
        "id": "R12c-scope-web",
        "name": "Out-Of-Scope Web Fetch",
        "condition": {"resource_in_scope": False, "tool_prefix": "web."},
        "action": "BLOCK",
        "severity": "high",
        "risk_score": 75,
        "reason": "URL '{resource}' is outside the authorized web scope for {tool}",
    },
    {
        # Generic fallback: local reads (e.g. file.read) outside the path allowlist.
        "id": "R12-resource-out-of-scope",
        "name": "Resource Out Of Scope",
        "condition": {"resource_in_scope": False},
        "action": "BLOCK",
        "severity": "medium",
        "risk_score": 60,
        "reason": "Resource '{resource}' is outside the authorized scope for {tool}",
    },
    {
        "id": "R6-untrusted-email-external-write",
        "name": "Untrusted Email + External Write",
        "condition": {
            "untrusted_source": "untrusted.email",
            "side_effect": "external_write",
        },
        "action": "BLOCK",
        "severity": "critical",
        "risk_score": 80,
        "reason": "External write influenced by untrusted email content",
    },
    {
        "id": "R7-untrusted-web-external-write",
        "name": "Untrusted Web + External Write",
        "condition": {
            "untrusted_source": "untrusted.web",
            "side_effect": "external_write",
        },
        "action": "BLOCK",
        "severity": "critical",
        "risk_score": 80,
        "reason": "External write influenced by untrusted web content",
    },
    {
        "id": "R8-secret-external-write",
        "name": "Secret + External Write",
        "condition": {
            "has_secret_data": True,
            "side_effect": "external_write",
        },
        "action": "BLOCK",
        "severity": "critical",
        "risk_score": 80,
        "reason": "Secret data may flow to external destination",
    },
    {
        "id": "R9-shell-approval",
        "name": "Shell Execution Approval",
        "condition": {"tool_prefix": "shell."},
        "action": "REQUIRE_APPROVAL",
        "severity": "high",
        "risk_score": 60,
        "reason": "Shell execution requires human approval",
    },
    {
        "id": "R10-unknown-tool",
        "name": "Unknown Tool",
        "condition": {"tool_unknown": True},
        "action": "BLOCK",
        "severity": "high",
        "risk_score": 50,
        "reason": "Tool '{tool}' is not registered",
    },
    {
        "id": "R11-secret-read-approval",
        "name": "Secret/Critical Read Approval",
        "condition": {"sensitivity": "critical", "side_effect": "read"},
        "action": "REQUIRE_APPROVAL",
        "severity": "high",
        "risk_score": 60,
        "reason": "Reading sensitive resource via '{tool}' requires human approval",
    },
]


class PolicyConfig:
    """Loads and evaluates policy rules from configuration."""

    def __init__(self, rules: Optional[list[dict[str, Any]]] = None) -> None:
        self.rules = rules or DEFAULT_POLICY_RULES

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PolicyConfig":
        """Load policy rules from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        rules = data.get("rules", DEFAULT_POLICY_RULES)
        return cls(rules=rules)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolicyConfig":
        """Load policy rules from a dict."""
        rules = data.get("rules", DEFAULT_POLICY_RULES)
        return cls(rules=rules)

    def evaluate_rule(
        self,
        rule: dict[str, Any],
        context: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """Evaluate a single rule against context.

        Returns {action, severity, risk_score, reason} if matched, None otherwise.
        """
        condition = rule.get("condition", {})
        matched = True

        for key, expected in condition.items():
            if key == "passport_valid":
                if context.get("passport_valid") != expected:
                    matched = False
                    break
            elif key == "signature_valid":
                if context.get("signature_valid") != expected:
                    matched = False
                    break
            elif key == "capability_valid":
                if context.get("capability_valid") != expected:
                    matched = False
                    break
            elif key == "tool_not_in_allowed":
                tool = context.get("tool", "")
                allowed = context.get("allowed_actions", [])
                if (tool not in allowed) != expected:
                    matched = False
                    break
            elif key == "tool_in_forbidden":
                tool = context.get("tool", "")
                forbidden = context.get("forbidden_actions", [])
                if (tool in forbidden) != expected:
                    matched = False
                    break
            elif key == "untrusted_source":
                influenced_by = context.get("influenced_by", [])
                if expected not in influenced_by:
                    matched = False
                    break
            elif key == "side_effect":
                if context.get("side_effect") != expected:
                    matched = False
                    break
            elif key == "sensitivity":
                if context.get("sensitivity") != expected:
                    matched = False
                    break
            elif key == "has_secret_data":
                uses_data = context.get("uses_data", [])
                influenced_by = context.get("influenced_by", [])
                has_secret = "secret" in uses_data or "secret" in influenced_by
                if has_secret != expected:
                    matched = False
                    break
            elif key == "tool_prefix":
                tool = context.get("tool", "")
                if not tool.startswith(expected):
                    matched = False
                    break
            elif key == "tool_unknown":
                # tool_unknown=True means the tool is NOT in the registry
                is_unknown = context.get("tool_unknown", False)
                if is_unknown != expected:
                    matched = False
                    break
            elif key == "resource_in_scope":
                if context.get("resource_in_scope", True) != expected:
                    matched = False
                    break

        if not matched:
            return None

        # Format reason with context
        reason_template = rule.get("reason", "")
        try:
            reason = reason_template.format(**context)
        except (KeyError, IndexError):
            reason = reason_template

        return {
            "action": rule.get("action", "BLOCK"),
            "severity": rule.get("severity", "medium"),
            "risk_score": rule.get("risk_score", 50),
            "reason": reason,
        }
