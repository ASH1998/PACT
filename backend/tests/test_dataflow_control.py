"""Structural enforcement tests — no keyword/blocklist matching involved.

These assert PACT's *data-flow* controls:
  1. Reading a critical-sensitivity resource requires human approval (R11),
     regardless of the resource's name.
  2. Once a run reads a secret, ANY subsequent external write is blocked by
     taint propagation — the file name and the destination address are
     irrelevant, which is the point: security comes from the data flow, not
     from recognizing ".env" or "attacker@gmail.com".
"""

from app.core.policy_config import PolicyConfig
from app.core.registry import ToolRegistry
from app.services.configurable_policy import ConfigurablePolicyService
from app.services.provenance import ProvenanceService


def _registry():
    reg = ToolRegistry()
    reg.register_tool(
        "file.read_secret",
        {"display_name": "s", "side_effect": "read", "sensitivity": "critical",
         "output_provenance": ["secret"]},
        fn=lambda **k: {},
    )
    reg.register_tool(
        "file.read",
        {"display_name": "f", "side_effect": "read", "sensitivity": "low",
         "output_provenance": ["internal.data"]},
        fn=lambda **k: {},
    )
    reg.register_tool(
        "email.send",
        {"display_name": "e", "side_effect": "external_write", "sensitivity": "high",
         "output_provenance": ["external_write"]},
        fn=lambda **k: {},
    )
    return reg


def test_critical_read_requires_approval_regardless_of_name():
    pol = ConfigurablePolicyService(config=PolicyConfig(), tool_registry=_registry())
    d = pol.evaluate(
        "file.read_secret",
        allowed_actions=["file.read_secret"],
        forbidden_actions=[],
        provenance={"influenced_by": [], "uses_data": []},
    )
    assert d.decision.value == "REQUIRE_APPROVAL"
    assert d.risk_score >= 60


def test_plain_read_still_allowed():
    pol = ConfigurablePolicyService(config=PolicyConfig(), tool_registry=_registry())
    d = pol.evaluate(
        "file.read",
        allowed_actions=["file.read"],
        forbidden_actions=[],
        provenance={"influenced_by": [], "uses_data": []},
    )
    assert d.decision.value == "ALLOW"


def test_secret_taint_blocks_later_external_write_without_keywords():
    """Read an innocuously-named secret, then try to send to an arbitrary
    address. The send is blocked purely by taint propagation."""
    reg = _registry()
    pol = ConfigurablePolicyService(config=PolicyConfig(), tool_registry=reg)
    prov = ProvenanceService()
    run = "run_dataflow_test"
    prov.start_run(run)

    # Step 0: read a secret from a file with a totally innocuous name
    prov.record_step(run, "file.read_secret", step_id=0, resource="notes.txt")

    # Step 1: attempt to email an arbitrary recipient
    prov.record_step(run, "email.send", step_id=1, resource="someone@example.org")
    send_prov = prov.build_provenance(run, "email.send")
    decision = pol.evaluate(
        "email.send",
        allowed_actions=["file.read_secret", "email.send"],
        forbidden_actions=[],
        provenance=send_prov,
    )

    assert "secret" in send_prov["influenced_by"]
    assert decision.decision.value == "BLOCK"
    assert any("secret" in r.lower() for r in decision.reasons)


def test_clean_external_write_is_allowed():
    """An external write with no secret/untrusted taint is allowed — the
    control blocks tainted flows, not all sends."""
    reg = _registry()
    pol = ConfigurablePolicyService(config=PolicyConfig(), tool_registry=reg)
    prov = ProvenanceService()
    run = "run_clean_test"
    prov.start_run(run)
    prov.record_step(run, "email.send", step_id=0, resource="someone@example.org")
    send_prov = prov.build_provenance(run, "email.send")
    decision = pol.evaluate(
        "email.send",
        allowed_actions=["email.send"],
        forbidden_actions=[],
        provenance=send_prov,
    )
    assert decision.decision.value == "ALLOW"
