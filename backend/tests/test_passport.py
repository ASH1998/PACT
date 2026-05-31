"""Tests for passport service."""

import pytest
from app.services.passport import PassportService
from app.crypto import generate_keypair


@pytest.fixture
def issuer_keys():
    """Generate a stable issuer keypair for testing."""
    return generate_keypair()


@pytest.fixture
def passport_service(issuer_keys):
    """Create a PassportService with deterministic issuer keys."""
    private, public = issuer_keys
    return PassportService(private, public)


async def test_create_passport_returns_valid_passport(passport_service, setup_db):
    """create_passport returns a dict with all expected fields."""
    from app.database import async_session
    async with async_session() as db:
        result = await passport_service.create_passport(
            db=db,
            agent_id="agent_test_1",
            owner="test-owner",
            agent_type="assistant",
            allowed_domains=["example.com"],
            risk_tier="medium",
        )

    assert "passport" in result
    assert "agent_private_key" in result
    passport = result["passport"]
    assert passport["agent_id"] == "agent_test_1"
    assert passport["owner"] == "test-owner"
    assert passport["agent_type"] == "assistant"
    assert passport["public_key"]
    assert passport["issuer_signature"]
    assert passport["allowed_domains"] == ["example.com"]


async def test_verify_passport_valid_signature(passport_service, setup_db):
    """A freshly created passport passes verification."""
    from app.database import async_session
    async with async_session() as db:
        result = await passport_service.create_passport(
            db=db,
            agent_id="agent_verify_ok",
            owner="test-owner",
            agent_type="assistant",
            allowed_domains=[],
            risk_tier="low",
        )

    passport = result["passport"]
    valid, reason = await passport_service.verify_passport(passport)
    assert valid is True
    assert reason == "Valid"


async def test_verify_passport_invalid_signature_rejects(passport_service, setup_db):
    """Tampering with the passport data invalidates the issuer signature."""
    from app.database import async_session
    async with async_session() as db:
        result = await passport_service.create_passport(
            db=db,
            agent_id="agent_verify_bad",
            owner="test-owner",
            agent_type="assistant",
            allowed_domains=[],
            risk_tier="low",
        )

    passport = result["passport"]
    # Tamper with the passport
    passport["owner"] = "EVIL_OWNER"
    valid, reason = await passport_service.verify_passport(passport)
    assert valid is False
    assert "signature" in reason.lower()


async def test_create_passport_stores_in_db(passport_service, setup_db):
    """create_passport persists the agent in the database and get_passport retrieves it."""
    from app.database import async_session
    async with async_session() as db:
        await passport_service.create_passport(
            db=db,
            agent_id="agent_stored",
            owner="test-owner",
            agent_type="generic",
            allowed_domains=["example.org"],
            risk_tier="high",
        )

    async with async_session() as db:
        stored = await passport_service.get_passport(db, "agent_stored")

    assert stored is not None
    assert stored["agent_id"] == "agent_stored"
    assert stored["owner"] == "test-owner"
    assert stored["risk_tier"] == "high"
