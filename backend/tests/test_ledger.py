"""Tests for ledger service."""

import pytest
from app.services.ledger import LedgerService
from app.database import async_session


@pytest.fixture
def ledger_service():
    return LedgerService()


def _base_action(**overrides):
    """Return default action kwargs, with optional overrides."""
    defaults = dict(
        run_id="run_ledger_test",
        step_id=0,
        agent_id="agent_ledger_1",
        tool="email.read",
        args_digest="sha256:args_abc",
        intent_hash="sha256:intent_abc",
        capability_token_hash="sha256:cap_abc",
        provenance={"influenced_by": ["trusted.user"], "uses_data": [], "side_effect": None},
        parent_action_hash=None,
        agent_signature="sig_placeholder",
        status="allowed",
    )
    defaults.update(overrides)
    return defaults


async def test_append_action_generates_hash(ledger_service, setup_db):
    """append_action returns a sha256 hash string."""
    async with async_session() as db:
        action_hash = await ledger_service.append_action(db, **_base_action())

    assert action_hash.startswith("sha256:")
    assert len(action_hash) > 10


async def test_chain_links_correctly(ledger_service, setup_db):
    """Two actions: the second has parent_action_hash == first action_hash."""
    async with async_session() as db:
        hash1 = await ledger_service.append_action(db, **_base_action(step_id=0))
        hash2 = await ledger_service.append_action(
            db, **_base_action(step_id=1, parent_action_hash=hash1)
        )

    assert hash1 != hash2

    async with async_session() as db:
        chain = await ledger_service.get_chain(db, "run_ledger_test")

    assert len(chain) == 2
    assert chain[0]["parent_action_hash"] is None
    assert chain[1]["parent_action_hash"] == hash1


async def test_verify_chain_valid(ledger_service, setup_db):
    """verify_chain returns (True, []) for a correctly linked chain."""
    async with async_session() as db:
        hash1 = await ledger_service.append_action(db, **_base_action(step_id=0))
        await ledger_service.append_action(
            db, **_base_action(step_id=1, parent_action_hash=hash1)
        )

    async with async_session() as db:
        valid, issues = await ledger_service.verify_chain(db, "run_ledger_test")

    assert valid is True
    assert issues == []
