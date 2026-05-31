from __future__ import annotations
"""Policy Service — evaluate action envelopes against PACT security rules."""


from app.schemas import Decision, Severity, PolicyDecision


def compute_risk_score(
    has_invalid_passport: bool = False,
    has_invalid_signature: bool = False,
    has_capability_mismatch: bool = False,
    has_intent_mismatch: bool = False,
    untrusted_influences: list[str] | None = None,
    has_external_write: bool = False,
    has_secret_usage: bool = False,
) -> tuple[int, Severity]:
    """Compute a risk score (0-100) and severity from policy evaluation flags."""
    score = 0

    if has_invalid_passport or has_invalid_signature:
        score += 100
    if has_capability_mismatch:
        score += 60
    if has_intent_mismatch:
        score += 50
    if untrusted_influences:
        score += 20 * len(untrusted_influences)
    if has_external_write:
        score += 30
    if has_secret_usage:
        score += 40

    score = min(score, 100)

    if score >= 90:
        severity = Severity.CRITICAL
    elif score >= 60:
        severity = Severity.HIGH
    elif score >= 25:
        severity = Severity.MEDIUM
    else:
        severity = Severity.LOW

    return score, severity


class PolicyService:
    """Evaluates PACT action envelopes against security rules."""

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
        """Evaluate an action and return a policy decision."""
        reasons: list[str] = []
        has_invalid_passport = False
        has_invalid_signature = False
        has_capability_mismatch = False
        has_intent_mismatch = False
        has_resource_violation = not resource_in_scope

        # R1: Passport
        if not passport_valid:
            has_invalid_passport = True
            reasons.append(f"Invalid agent passport: {passport_reason}")

        # R2: Signature
        if not signature_valid:
            has_invalid_signature = True
            reasons.append("Invalid action signature")

        # R3: Capability
        if not capability_valid:
            has_capability_mismatch = True
            reasons.append(f"Capability token invalid: {capability_reason}")

        # R4/R5: Intent alignment
        if tool not in allowed_actions:
            has_intent_mismatch = True
            reasons.append(f"{tool} not allowed by intent contract")
        if tool in forbidden_actions:
            has_intent_mismatch = True
            reasons.append(f"{tool} is explicitly forbidden by intent contract")

        # Provenance analysis
        influenced_by = provenance.get("influenced_by", [])
        uses_data = provenance.get("uses_data", [])
        side_effect = provenance.get("side_effect")

        untrusted_influences = [
            label for label in influenced_by
            if label.startswith("untrusted.")
        ]
        has_external_write = side_effect == "external_write"
        has_secret_usage = "secret" in uses_data or "secret" in influenced_by

        # R6: untrusted.email + external_write
        if "untrusted.email" in influenced_by and has_external_write:
            reasons.append("External write influenced by untrusted email content")

        # R7: untrusted.web + external_write
        if "untrusted.web" in influenced_by and has_external_write:
            reasons.append("External write influenced by untrusted web content")

        # R8: secret + external_write
        if has_secret_usage and has_external_write:
            reasons.append("Secret data may flow to external destination")

        # R9: shell requires approval
        if tool == "shell.execute_mock":
            reasons.append("Shell execution requires human approval")

        # R12: requested resource outside operator-authorized scope
        if has_resource_violation:
            reasons.append(f"Resource '{resource}' is outside the authorized scope for {tool}")

        # Compute risk score
        risk_score, severity = compute_risk_score(
            has_invalid_passport=has_invalid_passport,
            has_invalid_signature=has_invalid_signature,
            has_capability_mismatch=has_capability_mismatch,
            has_intent_mismatch=has_intent_mismatch,
            untrusted_influences=untrusted_influences,
            has_external_write=has_external_write,
            has_secret_usage=has_secret_usage,
        )

        if has_resource_violation:
            risk_score = max(risk_score, 70)
            if severity not in (Severity.HIGH, Severity.CRITICAL):
                severity = Severity.HIGH

        # Determine decision
        if has_invalid_passport or has_invalid_signature:
            decision = Decision.BLOCK
        elif has_capability_mismatch:
            decision = Decision.BLOCK
        elif has_intent_mismatch:
            decision = Decision.BLOCK
        elif has_resource_violation:
            decision = Decision.BLOCK
        elif "untrusted.email" in influenced_by and has_external_write:
            decision = Decision.BLOCK
        elif "untrusted.web" in influenced_by and has_external_write:
            decision = Decision.BLOCK
        elif has_secret_usage and has_external_write:
            decision = Decision.BLOCK
        elif tool == "shell.execute_mock":
            decision = Decision.REQUIRE_APPROVAL
        else:
            decision = Decision.ALLOW
            if not reasons:
                reasons.append("Action is valid and aligned with intent")

        return PolicyDecision(
            decision=decision,
            risk_score=risk_score,
            severity=severity,
            reasons=reasons,
        )
