"""Tests for action envelope service."""

import pytest
from app.services.envelope import EnvelopeService
from app.crypto import generate_keypair


@pytest.fixture
def keys():
    """Generate a keypair for signing envelopes."""
    return generate_keypair()


@pytest.fixture
def envelope_service():
    return EnvelopeService()


def _make_envelope_args(keys):
    """Return common kwargs for create_envelope."""
    private, _ = keys
    return dict(
        agent_id="agent_env_1",
        agent_private_key=private,
        run_id="run_test_001",
        step_id=0,
        tool="email.read",
        args={"email_id": "msg_42"},
        intent_hash="sha256:intent_abc",
        capability_token_hash="sha256:cap_def",
        provenance={
            "influenced_by": ["trusted.user"],
            "uses_data": ["untrusted.email"],
            "side_effect": None,
        },
    )


def test_create_envelope_has_all_fields(envelope_service, keys):
    """create_envelope returns a dict with all PACT envelope fields."""
    env = envelope_service.create_envelope(**_make_envelope_args(keys))

    assert env["protocol"] == "PACT/0.1"
    assert env["run_id"] == "run_test_001"
    assert env["step_id"] == 0
    assert env["agent_id"] == "agent_env_1"
    assert env["tool"] == "email.read"
    assert env["args"] == {"email_id": "msg_42"}
    assert env["args_digest"].startswith("sha256:")
    assert env["intent_hash"] == "sha256:intent_abc"
    assert env["capability_token_hash"] == "sha256:cap_def"
    assert env["agent_signature"]
    assert env["timestamp"]


def test_create_envelope_signature_valid(envelope_service, keys):
    """The signature produced by create_envelope can be verified."""
    _, public = keys
    env = envelope_service.create_envelope(**_make_envelope_args(keys))
    valid, reason = envelope_service.verify_envelope(env, public)
    assert valid is True
    assert reason == "Valid"


def test_verify_envelope_accepts_valid(envelope_service, keys):
    """verify_envelope accepts an envelope signed with the correct key."""
    _, public = keys
    env = envelope_service.create_envelope(**_make_envelope_args(keys))
    valid, _ = envelope_service.verify_envelope(env, public)
    assert valid is True


def test_verify_envelope_rejects_tampered(envelope_service, keys):
    """Modifying args after signing causes verification to fail."""
    _, public = keys
    env = envelope_service.create_envelope(**_make_envelope_args(keys))

    # Tamper with args
    env["args"] = {"email_id": "msg_999"}

    valid, reason = envelope_service.verify_envelope(env, public)
    assert valid is False
    assert "mismatch" in reason.lower() or "signature" in reason.lower()
