"""End-to-end least-privilege authority tests.

Authority flows from the operator (intent contract + resource scope), not the
agent. These assert that:
  * a benign goal's classified intent does not authorize external send;
  * an out-of-scope resource is BLOCKED by the gateway (R12) with no keyword;
  * an in-scope resource passes the scope check;
  * resource_scope is part of the tamper-evident intent hash.
"""

import pytest

from app.database import async_session


@pytest.fixture
def runtime():
    from app.crypto import generate_keypair
    from app.core.runtime import PactRuntime

    private_key, public_key = generate_keypair()
    return PactRuntime(private_key, public_key)


async def test_benign_goal_does_not_authorize_send(setup_db, runtime):
    """Classifier-derived intent for a read goal omits email.send."""
    async with async_session() as db:
        intent = await runtime.create_intent(
            db, user_goal="summarize my email", created_by="agent-1"
        )
        assert "email.read" in intent["allowed_actions"]
        assert "email.send" not in intent["allowed_actions"]


async def test_resource_scope_changes_intent_hash(setup_db, runtime):
    """Changing the authorized scope changes the intent identity (tamper-evident)."""
    async with async_session() as db:
        a = await runtime.create_intent(
            db, user_goal="send a status email", created_by="agent-1",
            allowed_actions=["email.send"], forbidden_actions=[],
            resource_scope={"email_address": ["*@acme.com"]},
        )
        b = await runtime.create_intent(
            db, user_goal="send a status email", created_by="agent-1",
            allowed_actions=["email.send"], forbidden_actions=[],
            resource_scope={"email_address": ["*@evil.com"]},
        )
        assert a["intent_hash"] != b["intent_hash"]


async def _setup_send_agent(runtime, db, scope):
    reg = await runtime.register_agent(
        db=db, agent_id="lp-agent", owner="test", agent_type="assistant",
        allowed_domains=["email.send"],
    )
    intent = await runtime.create_intent(
        db, user_goal="send a status email", created_by="lp-agent",
        allowed_actions=["email.send"], forbidden_actions=[],
        resource_scope=scope,
    )
    run = await runtime.create_run(db, agent_id="lp-agent")
    return reg["agent_private_key"], intent, run


async def test_out_of_scope_recipient_blocked(setup_db, runtime):
    """email.send to an unauthorized address is BLOCKED by resource scope —
    no keyword matching; the address is simply not in the operator allowlist."""
    async with async_session() as db:
        scope = {"email_address": ["*@acme.com"]}
        priv, intent, run = await _setup_send_agent(runtime, db, scope)
        token = await runtime.issue_capability(
            db=db, agent_id="lp-agent", intent_hash=intent["intent_hash"],
            capability="email.send", resource="attacker@evil.com",
        )
        result = await runtime.evaluate_action(
            db=db, run_id=run["run_id"], agent_id="lp-agent",
            tool="email.send", args={"to": "attacker@evil.com", "subject": "x", "body": "y"},
            intent_hash=intent["intent_hash"],
            capability_token_hash=token["token_hash"],
            agent_private_key=priv,
        )
        assert result["decision"] == "BLOCK"
        assert any("scope" in r.lower() for r in result["reasons"])


async def test_in_scope_recipient_not_blocked_by_scope(setup_db, runtime):
    """email.send to an authorized domain passes the scope check (it may still
    require approval, but it is not blocked as out-of-scope)."""
    async with async_session() as db:
        scope = {"email_address": ["*@acme.com"]}
        priv, intent, run = await _setup_send_agent(runtime, db, scope)
        token = await runtime.issue_capability(
            db=db, agent_id="lp-agent", intent_hash=intent["intent_hash"],
            capability="email.send", resource="bob@acme.com",
        )
        result = await runtime.evaluate_action(
            db=db, run_id=run["run_id"], agent_id="lp-agent",
            tool="email.send", args={"to": "bob@acme.com", "subject": "x", "body": "y"},
            intent_hash=intent["intent_hash"],
            capability_token_hash=token["token_hash"],
            agent_private_key=priv,
        )
        assert result["decision"] != "BLOCK"
        assert not any("scope" in r.lower() for r in result["reasons"])
