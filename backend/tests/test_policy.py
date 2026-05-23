"""Test: policy engine — risk scoring and decision logic."""

import pytest
from app.services.policy import PolicyService, compute_risk_score
from app.schemas import Decision, Severity


class TestRiskScoring:
    def test_base_score_zero(self):
        score, severity = compute_risk_score()
        assert score == 0
        assert severity == Severity.LOW

    def test_invalid_passport_maxes_score(self):
        score, _ = compute_risk_score(has_invalid_passport=True)
        assert score == 100

    def test_untrusted_influence_adds(self):
        score, _ = compute_risk_score(untrusted_influences=["untrusted.email"])
        assert score == 20

    def test_multiple_untrusted(self):
        score, _ = compute_risk_score(
            untrusted_influences=["untrusted.email", "untrusted.web"]
        )
        assert score == 40

    def test_secret_plus_external_write(self):
        score, _ = compute_risk_score(has_secret_usage=True, has_external_write=True)
        assert score == 70

    def test_capped_at_100(self):
        score, _ = compute_risk_score(
            has_invalid_passport=True,
            has_intent_mismatch=True,
            has_external_write=True,
        )
        assert score == 100

    def test_severity_critical(self):
        _, severity = compute_risk_score(has_invalid_passport=True)
        assert severity == Severity.CRITICAL

    def test_severity_high(self):
        _, severity = compute_risk_score(has_capability_mismatch=True)
        assert severity == Severity.HIGH

    def test_severity_medium(self):
        _, severity = compute_risk_score(untrusted_influences=["untrusted.email"])
        assert severity == Severity.MEDIUM


class TestPolicyEvaluation:
    def test_valid_email_read_allows(self):
        svc = PolicyService()
        decision = svc.evaluate(
            tool="email.read",
            allowed_actions=["email.read", "summarize", "respond_to_user"],
            forbidden_actions=["email.send"],
            provenance={"influenced_by": ["trusted.user"], "uses_data": [], "side_effect": None},
        )
        assert decision.decision == Decision.ALLOW
        assert decision.risk_score == 0
        assert decision.severity == Severity.LOW

    def test_tool_outside_intent_blocks(self):
        svc = PolicyService()
        decision = svc.evaluate(
            tool="email.send",
            allowed_actions=["email.read", "summarize", "respond_to_user"],
            forbidden_actions=["email.send"],
            provenance={"influenced_by": ["trusted.user"], "uses_data": [], "side_effect": None},
        )
        assert decision.decision == Decision.BLOCK
        assert decision.risk_score >= 50

    def test_untrusted_email_to_external_write_blocks(self):
        svc = PolicyService()
        decision = svc.evaluate(
            tool="email.send",
            allowed_actions=["email.send", "respond_to_user"],
            forbidden_actions=[],
            provenance={
                "influenced_by": ["untrusted.email"],
                "uses_data": [],
                "side_effect": "external_write",
            },
        )
        assert decision.decision == Decision.BLOCK
        assert any("untrusted email" in r.lower() for r in decision.reasons)

    def test_secret_to_external_write_blocks(self):
        svc = PolicyService()
        decision = svc.evaluate(
            tool="email.send",
            allowed_actions=["email.send", "respond_to_user"],
            forbidden_actions=[],
            provenance={
                "influenced_by": ["trusted.user", "secret"],
                "uses_data": ["secret"],
                "side_effect": "external_write",
            },
        )
        assert decision.decision == Decision.BLOCK
        assert any("secret" in r.lower() for r in decision.reasons)

    def test_shell_requires_approval(self):
        svc = PolicyService()
        decision = svc.evaluate(
            tool="shell.execute_mock",
            allowed_actions=["shell.execute_mock", "respond_to_user"],
            forbidden_actions=[],
            provenance={"influenced_by": ["trusted.user"], "uses_data": [], "side_effect": None},
        )
        assert decision.decision == Decision.REQUIRE_APPROVAL

    def test_invalid_passport_blocks(self):
        svc = PolicyService()
        decision = svc.evaluate(
            tool="email.read",
            allowed_actions=["email.read"],
            forbidden_actions=[],
            provenance={"influenced_by": ["trusted.user"], "uses_data": [], "side_effect": None},
            passport_valid=False,
            passport_reason="Passport expired",
        )
        assert decision.decision == Decision.BLOCK
        assert decision.risk_score == 100

    def test_invalid_signature_blocks(self):
        svc = PolicyService()
        decision = svc.evaluate(
            tool="email.read",
            allowed_actions=["email.read"],
            forbidden_actions=[],
            provenance={"influenced_by": ["trusted.user"], "uses_data": [], "side_effect": None},
            signature_valid=False,
        )
        assert decision.decision == Decision.BLOCK
