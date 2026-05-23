"""Tests for capability token service."""

import asyncio
import pytest
from app.services.capability import CapabilityService
from app.crypto import generate_keypair


@pytest.fixture
def cap_service():
    """Create a CapabilityService with a stable keypair."""
    private, public = generate_keypair()
    return CapabilityService(private, public)


async def test_issue_token_returns_valid_token(cap_service, setup_db):
    """issue_token returns a dict with all expected fields."""
    from app.database import async_session
    async with async_session() as db:
        result = await cap_service.issue_token(
            db=db,
            agent_id="agent_cap_1",
            intent_hash="sha256:abc123",
            capability="email.read",
            resource="inbox",
            max_uses=5,
            ttl_seconds=300,
        )

    assert result["token_hash"].startswith("sha256:")
    assert result["agent_id"] == "agent_cap_1"
    assert result["capability"] == "email.read"
    assert result["resource"] == "inbox"
    assert result["max_uses"] == 5
    assert result["uses_remaining"] == 5
    assert result["signature"]


async def test_validate_token_accepts_valid(cap_service, setup_db):
    """A freshly issued token passes validation."""
    from app.database import async_session
    async with async_session() as db:
        result = await cap_service.issue_token(
            db=db,
            agent_id="agent_cap_2",
            intent_hash="sha256:def456",
            capability="web.read",
            resource="https://example.com",
        )
        valid, reason = await cap_service.validate_token(
            db=db,
            token_hash=result["token_hash"],
            agent_id="agent_cap_2",
            intent_hash="sha256:def456",
            capability="web.read",
        )

    assert valid is True
    assert reason == "Valid"


async def test_validate_token_rejects_expired(cap_service, setup_db):
    """A token with ttl_seconds=0 is immediately expired."""
    from app.database import async_session
    async with async_session() as db:
        result = await cap_service.issue_token(
            db=db,
            agent_id="agent_cap_exp",
            intent_hash="sha256:exp",
            capability="email.read",
            ttl_seconds=0,
        )
        # Sleep to ensure the token is in the past
        await asyncio.sleep(0.05)
        valid, reason = await cap_service.validate_token(
            db=db,
            token_hash=result["token_hash"],
            agent_id="agent_cap_exp",
            intent_hash="sha256:exp",
            capability="email.read",
        )

    assert valid is False
    assert "expired" in reason.lower()


async def test_validate_token_rejects_wrong_agent(cap_service, setup_db):
    """Validation fails when the agent_id doesn't match."""
    from app.database import async_session
    async with async_session() as db:
        result = await cap_service.issue_token(
            db=db,
            agent_id="agent_correct",
            intent_hash="sha256:xyz",
            capability="email.read",
        )
        valid, reason = await cap_service.validate_token(
            db=db,
            token_hash=result["token_hash"],
            agent_id="agent_wrong",
            intent_hash="sha256:xyz",
            capability="email.read",
        )

    assert valid is False
    assert "agent" in reason.lower() or "different" in reason.lower()


async def test_validate_token_rejects_wrong_capability(cap_service, setup_db):
    """Validation fails when the capability doesn't match."""
    from app.database import async_session
    async with async_session() as db:
        result = await cap_service.issue_token(
            db=db,
            agent_id="agent_cap_wc",
            intent_hash="sha256:wc",
            capability="email.read",
        )
        valid, reason = await cap_service.validate_token(
            db=db,
            token_hash=result["token_hash"],
            agent_id="agent_cap_wc",
            intent_hash="sha256:wc",
            capability="email.send",
        )

    assert valid is False
    assert "email.read" in reason or "email.send" in reason


async def test_consume_use_decrements_count(cap_service, setup_db):
    """consume_use decrements uses_remaining by 1."""
    from app.database import async_session
    async with async_session() as db:
        result = await cap_service.issue_token(
            db=db,
            agent_id="agent_consume",
            intent_hash="sha256:cons",
            capability="web.read",
            max_uses=3,
        )
        token_hash = result["token_hash"]

        success = await cap_service.consume_use(db, token_hash)
        assert success is True

        token = await cap_service.get_token(db, token_hash)
        assert token["uses_remaining"] == 2


async def test_consume_use_rejects_exhausted(cap_service, setup_db):
    """consume_use returns False when token is exhausted."""
    from app.database import async_session
    async with async_session() as db:
        result = await cap_service.issue_token(
            db=db,
            agent_id="agent_exhaust",
            intent_hash="sha256:exh",
            capability="web.read",
            max_uses=1,
        )
        token_hash = result["token_hash"]

        # Consume the single use
        success1 = await cap_service.consume_use(db, token_hash)
        assert success1 is True

        # Second attempt should fail
        success2 = await cap_service.consume_use(db, token_hash)
        assert success2 is False
