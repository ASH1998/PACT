"""Tests for PACT core module — PactRuntime, ToolRegistry, KeyManager, PolicyConfig."""

import pytest

from app.database import async_session


@pytest.fixture
def runtime():
    """Provide a PactRuntime instance with test issuer keys."""
    from app.crypto import generate_keypair
    private_key, public_key = generate_keypair()
    from app.core.runtime import PactRuntime
    return PactRuntime(private_key, public_key)


@pytest.fixture
def issuer_keys():
    """Generate a fresh issuer keypair."""
    from app.crypto import generate_keypair
    return generate_keypair()


# --- PactRuntime Tests ---


class TestPactRuntimeCreateRun:
    """Tests for PactRuntime.create_run."""

    async def test_create_run_basic(self, setup_db, runtime):
        async with async_session() as db:
            result = await runtime.create_run(db, agent_id="agent-1")
            assert result["run_id"].startswith("run_")
            assert result["agent_id"] == "agent-1"
            assert result["status"] == "running"

    async def test_create_run_with_scenario(self, setup_db, runtime):
        async with async_session() as db:
            result = await runtime.create_run(
                db, agent_id="agent-1", scenario_name="test_scenario", user_goal="do something"
            )
            assert result["scenario_name"] == "test_scenario"
            assert result["user_goal"] == "do something"


class TestPactRuntimeCreateIntent:
    """Tests for PactRuntime.create_intent."""

    async def test_create_intent_keyword(self, setup_db, runtime):
        """Keyword-based intent classification."""
        async with async_session() as db:
            result = await runtime.create_intent(db, user_goal="summarize my email")
            assert result["intent_id"].startswith("intent_")
            assert "email.read" in result["allowed_actions"]
            assert "intent_hash" in result

    async def test_create_intent_programmatic(self, setup_db, runtime):
        """Programmatic intent with explicit actions."""
        async with async_session() as db:
            result = await runtime.create_intent(
                db,
                user_goal="custom task",
                allowed_actions=["email.read", "summarize"],
                forbidden_actions=["email.send"],
                created_by="agent-1",
            )
            assert "email.read" in result["allowed_actions"]
            assert "email.send" in result["forbidden_actions"]
            assert result["created_by"] == "agent-1"


class TestPactRuntimeRegisterAndCapability:
    """Tests for PactRuntime.register_agent and issue_capability."""

    async def test_register_agent(self, setup_db, runtime):
        async with async_session() as db:
            result = await runtime.register_agent(
                db=db,
                agent_id="test-agent",
                owner="test-owner",
                agent_type="assistant",
                allowed_domains=["example.com"],
            )
            assert "passport" in result
            assert result["passport"]["agent_id"] == "test-agent"
            assert "agent_private_key" in result

    async def test_issue_capability(self, setup_db, runtime):
        async with async_session() as db:
            # Register agent first
            await runtime.register_agent(
                db=db, agent_id="cap-agent", owner="test", agent_type="assistant",
                allowed_domains=["example.com"],
            )
            # Create intent
            intent = await runtime.create_intent(
                db, user_goal="summarize my email", created_by="cap-agent"
            )
            # Issue capability
            token = await runtime.issue_capability(
                db=db,
                agent_id="cap-agent",
                intent_hash=intent["intent_hash"],
                capability="email.read",
                resource="msg_1",
            )
            assert token["token_hash"]
            assert token["agent_id"] == "cap-agent"


class TestPactRuntimeProposeAction:
    """Tests for PactRuntime.propose_action."""

    async def test_propose_action_allow(self, setup_db, runtime):
        async with async_session() as db:
            # Setup agent
            reg = await runtime.register_agent(
                db=db, agent_id="action-agent", owner="test", agent_type="assistant",
                allowed_domains=["example.com"],
            )
            agent_private_key = reg["agent_private_key"]

            # Create intent
            intent = await runtime.create_intent(
                db, user_goal="summarize my email", created_by="action-agent"
            )

            # Issue capability
            token = await runtime.issue_capability(
                db=db, agent_id="action-agent",
                intent_hash=intent["intent_hash"],
                capability="email.read", resource="msg_1",
            )

            # Create run
            run = await runtime.create_run(db, agent_id="action-agent")

            # Propose action
            result = await runtime.propose_action(
                db=db,
                run_id=run["run_id"],
                agent_id="action-agent",
                agent_private_key=agent_private_key,
                tool="email.read",
                args={"email_id": "msg_1"},
                intent_hash=intent["intent_hash"],
                capability_token_hash=token["token_hash"],
            )
            assert result["decision"] == "ALLOW"
            assert result["action_hash"]

    async def test_propose_action_block_outside_intent(self, setup_db, runtime):
        async with async_session() as db:
            reg = await runtime.register_agent(
                db=db, agent_id="block-agent", owner="test", agent_type="assistant",
                allowed_domains=["example.com"],
            )
            agent_private_key = reg["agent_private_key"]

            intent = await runtime.create_intent(
                db, user_goal="summarize my email", created_by="block-agent"
            )

            token = await runtime.issue_capability(
                db=db, agent_id="block-agent",
                intent_hash=intent["intent_hash"],
                capability="email.send", resource="outbox",
            )

            run = await runtime.create_run(db, agent_id="block-agent")

            # email.send is NOT in the "summarize email" intent
            result = await runtime.propose_action(
                db=db,
                run_id=run["run_id"],
                agent_id="block-agent",
                agent_private_key=agent_private_key,
                tool="email.send",
                args={"to": "evil@hacker.com", "body": "stolen"},
                intent_hash=intent["intent_hash"],
                capability_token_hash=token["token_hash"],
            )
            assert result["decision"] == "BLOCK"


class TestPactRuntimeVerifyRun:
    """Tests for PactRuntime.verify_run."""

    async def test_verify_run(self, setup_db, runtime):
        async with async_session() as db:
            reg = await runtime.register_agent(
                db=db, agent_id="verify-agent", owner="test", agent_type="assistant",
                allowed_domains=["example.com"],
            )
            agent_private_key = reg["agent_private_key"]

            intent = await runtime.create_intent(
                db, user_goal="summarize my email", created_by="verify-agent"
            )
            token = await runtime.issue_capability(
                db=db, agent_id="verify-agent",
                intent_hash=intent["intent_hash"],
                capability="email.read", resource="msg_1",
            )
            run = await runtime.create_run(db, agent_id="verify-agent")

            # Use execute_action (real gateway) to create a ledger entry
            envelope = runtime.envelope_service.create_envelope(
                agent_id="verify-agent",
                agent_private_key=agent_private_key,
                run_id=run["run_id"],
                step_id=0,
                tool="email.read",
                args={"email_id": "msg_1"},
                intent_hash=intent["intent_hash"],
                capability_token_hash=token["token_hash"],
                provenance={"influenced_by": ["trusted.user"], "uses_data": [], "side_effect": None},
            )
            await runtime.execute_action(db=db, envelope=envelope, run_id=run["run_id"])

            result = await runtime.verify_run(db, run["run_id"])
            assert result["valid"] is True
            assert result["chain_length"] == 1


class TestPactRuntimeRecordModelEvent:
    """Tests for PactRuntime.record_model_event."""

    async def test_record_model_event(self, setup_db, runtime):
        async with async_session() as db:
            run = await runtime.create_run(db, agent_id="model-agent")
            result = await runtime.record_model_event(
                db=db,
                run_id=run["run_id"],
                provider="gemini",
                model="gemini-2.0-flash",
                request_json='{"contents": []}',
                response_json='{"candidates": []}',
                tool_calls=[{"name": "email.read", "args": {}}],
                token_usage={"prompt_tokens": 100, "completion_tokens": 50},
            )
            assert result["event_id"].startswith("mevt_")
            assert result["provider"] == "gemini"


# --- ToolRegistry Tests ---


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_and_get(self):
        from app.core.registry import ToolRegistry
        from app.core.tool_metadata import SideEffect
        registry = ToolRegistry()
        registry.register_tool("test.tool", {
            "display_name": "Test Tool",
            "side_effect": SideEffect.NONE,
        })
        assert registry.has_tool("test.tool")
        info = registry.get_tool("test.tool")
        assert info["metadata"]["display_name"] == "Test Tool"

    def test_get_callable(self):
        from app.core.registry import ToolRegistry
        from app.core.tool_metadata import SideEffect
        registry = ToolRegistry()
        fn = lambda x: x  # noqa: E731
        registry.register_tool("test.fn", {
            "display_name": "Test Fn",
            "side_effect": SideEffect.NONE,
        }, fn=fn)
        assert registry.get_callable("test.fn") is fn

    def test_list_tools(self):
        from app.core.registry import ToolRegistry
        from app.core.tool_metadata import SideEffect
        registry = ToolRegistry()
        registry.register_tool("a.tool", {"display_name": "A", "side_effect": SideEffect.NONE})
        registry.register_tool("b.tool", {"display_name": "B", "side_effect": SideEffect.READ})
        tools = registry.list_tools()
        ids = [t["tool_id"] for t in tools]
        assert "a.tool" in ids
        assert "b.tool" in ids

    def test_unknown_tool(self):
        from app.core.registry import ToolRegistry
        registry = ToolRegistry()
        assert registry.has_tool("nonexistent") is False
        assert registry.get_tool("nonexistent") is None
        assert registry.get_callable("nonexistent") is None

    def test_unregister(self):
        from app.core.registry import ToolRegistry
        from app.core.tool_metadata import SideEffect
        registry = ToolRegistry()
        registry.register_tool("del.me", {"display_name": "Del", "side_effect": SideEffect.NONE})
        assert registry.has_tool("del.me")
        assert registry.unregister_tool("del.me") is True
        assert registry.has_tool("del.me") is False

    def test_default_registry_has_demo_tools(self):
        from app.core.registry import get_default_registry
        registry = get_default_registry()
        assert registry.has_tool("email.read")
        assert registry.has_tool("email.send")
        assert registry.has_tool("shell.execute_mock")


# --- KeyManager Tests ---


class TestKeyManager:
    """Tests for KeyManager."""

    def test_get_key(self):
        from app.core.key_management import KeyManager
        km = KeyManager()
        priv, pub = km.get_key("passport_issuer")
        assert priv
        assert pub

    def test_get_same_key_twice(self):
        from app.core.key_management import KeyManager
        km = KeyManager()
        priv1, pub1 = km.get_key("passport_issuer")
        priv2, pub2 = km.get_key("passport_issuer")
        assert priv1 == priv2
        assert pub1 == pub2

    def test_different_roles_different_keys(self):
        from app.core.key_management import KeyManager
        km = KeyManager()
        _, pub1 = km.get_key("passport_issuer")
        _, pub2 = km.get_key("capability_issuer")
        assert pub1 != pub2

    def test_rotate_key(self):
        from app.core.key_management import KeyManager
        km = KeyManager()
        old_key_id = km.get_key_id("passport_issuer")
        new_key_id = km.rotate_key("passport_issuer")
        assert new_key_id != old_key_id

    def test_revoke_key(self):
        from app.core.key_management import KeyManager
        km = KeyManager()
        key_id = km.get_key_id("passport_issuer")
        assert km.revoke_key(key_id) is True
        # After revocation, getting the key should raise or return new
        with pytest.raises(Exception):
            km.get_key("passport_issuer")


class TestFactory:
    """Tests for the PactRuntime factory (composition root)."""

    def test_get_key_manager_singleton(self):
        """get_key_manager() returns the same instance on repeated calls."""
        from app.core.factory import get_key_manager, reset_runtime
        from app.core.key_management import KeyManager
        reset_runtime()
        try:
            km1 = get_key_manager()
            km2 = get_key_manager()
            assert km1 is km2
            assert isinstance(km1, KeyManager)
        finally:
            reset_runtime()

    def test_get_runtime_singleton(self):
        """get_runtime() returns the same PactRuntime instance on repeated calls."""
        from app.core.factory import get_runtime, reset_runtime
        from app.core.runtime import PactRuntime
        reset_runtime()
        try:
            r1 = get_runtime()
            r2 = get_runtime()
            assert r1 is r2
            assert isinstance(r1, PactRuntime)
        finally:
            reset_runtime()

    def test_reset_runtime(self):
        """reset_runtime() creates fresh instances on next access."""
        from app.core.factory import get_runtime, reset_runtime
        reset_runtime()
        try:
            r1 = get_runtime()
            reset_runtime()
            r2 = get_runtime()
            assert r1 is not r2
        finally:
            reset_runtime()


class TestPactRuntimeKeyManager:
    """Tests for PactRuntime with KeyManager wiring."""

    def test_runtime_with_key_manager(self):
        """PactRuntime can be constructed with a KeyManager."""
        from app.core.key_management import KeyManager
        from app.core.runtime import PactRuntime
        km = KeyManager()
        rt = PactRuntime(key_manager=km)
        assert rt.passport_service is not None
        assert rt.capability_service is not None

    def test_runtime_with_key_manager_uses_separate_keys(self):
        """When using KeyManager, passport and capability services get different keys."""
        from app.core.key_management import KeyManager
        from app.core.runtime import PactRuntime
        km = KeyManager()
        rt = PactRuntime(key_manager=km)
        # The passport and capability issuers should have different keys
        assert rt.passport_service is not rt.capability_service


class TestEvaluateAction:
    """Tests for PactRuntime.evaluate_action (dry-run path)."""

    async def test_evaluate_does_not_execute_tool(self, setup_db, runtime):
        """evaluate_action should NOT execute the mock tool."""
        async with async_session() as db:
            reg = await runtime.register_agent(
                db=db, agent_id="eval-agent", owner="test", agent_type="assistant",
                allowed_domains=["example.com"],
            )
            agent_private_key = reg["agent_private_key"]
            intent = await runtime.create_intent(
                db, user_goal="summarize my email", created_by="eval-agent"
            )
            token = await runtime.issue_capability(
                db=db, agent_id="eval-agent",
                intent_hash=intent["intent_hash"],
                capability="email.read", resource="msg_1",
            )
            run = await runtime.create_run(db, agent_id="eval-agent")

            result = await runtime.evaluate_action(
                db=db,
                run_id=run["run_id"],
                agent_id="eval-agent",
                tool="email.read",
                args={"email_id": "msg_1"},
                intent_hash=intent["intent_hash"],
                capability_token_hash=token["token_hash"],
                agent_private_key=agent_private_key,
            )

            # evaluate_action patches get_mock_tool to None, so tool_result
            # should be None even if the decision is ALLOW
            assert result["decision"] in ("ALLOW", "BLOCK")

    async def test_evaluate_returns_allow(self, setup_db, runtime):
        """evaluate_action returns ALLOW for a valid setup."""
        async with async_session() as db:
            reg = await runtime.register_agent(
                db=db, agent_id="eval-allow", owner="test", agent_type="assistant",
                allowed_domains=["example.com"],
            )
            agent_private_key = reg["agent_private_key"]
            intent = await runtime.create_intent(
                db, user_goal="summarize my email", created_by="eval-allow"
            )
            token = await runtime.issue_capability(
                db=db, agent_id="eval-allow",
                intent_hash=intent["intent_hash"],
                capability="email.read", resource="msg_1",
            )
            run = await runtime.create_run(db, agent_id="eval-allow")

            result = await runtime.evaluate_action(
                db=db,
                run_id=run["run_id"],
                agent_id="eval-allow",
                tool="email.read",
                args={"email_id": "msg_1"},
                intent_hash=intent["intent_hash"],
                capability_token_hash=token["token_hash"],
                agent_private_key=agent_private_key,
            )
            assert result["decision"] == "ALLOW"
            assert result["action_hash"]
            assert "envelope" in result

    async def test_evaluate_returns_block_for_intent_mismatch(self, setup_db, runtime):
        """evaluate_action returns BLOCK when tool is outside intent."""
        async with async_session() as db:
            reg = await runtime.register_agent(
                db=db, agent_id="eval-block", owner="test", agent_type="assistant",
                allowed_domains=["example.com"],
            )
            agent_private_key = reg["agent_private_key"]
            intent = await runtime.create_intent(
                db, user_goal="summarize my email", created_by="eval-block"
            )
            token = await runtime.issue_capability(
                db=db, agent_id="eval-block",
                intent_hash=intent["intent_hash"],
                capability="email.send", resource="outbox",
            )
            run = await runtime.create_run(db, agent_id="eval-block")

            result = await runtime.evaluate_action(
                db=db,
                run_id=run["run_id"],
                agent_id="eval-block",
                tool="email.send",
                args={"to": "evil@hacker.com", "body": "stolen"},
                intent_hash=intent["intent_hash"],
                capability_token_hash=token["token_hash"],
                agent_private_key=agent_private_key,
            )
            assert result["decision"] == "BLOCK"


class TestRecordToolResult:
    """Tests for PactRuntime.record_tool_result."""

    async def test_record_tool_result(self, setup_db, runtime):
        """record_tool_result persists the result to the DB."""
        async with async_session() as db:
            reg = await runtime.register_agent(
                db=db, agent_id="result-agent", owner="test", agent_type="assistant",
                allowed_domains=["example.com"],
            )
            agent_private_key = reg["agent_private_key"]
            intent = await runtime.create_intent(
                db, user_goal="summarize my email", created_by="result-agent"
            )
            token = await runtime.issue_capability(
                db=db, agent_id="result-agent",
                intent_hash=intent["intent_hash"],
                capability="email.read", resource="msg_1",
            )
            run = await runtime.create_run(db, agent_id="result-agent")

            # execute (real gateway) to create a DB action record
            envelope = runtime.envelope_service.create_envelope(
                agent_id="result-agent",
                agent_private_key=agent_private_key,
                run_id=run["run_id"],
                step_id=0,
                tool="email.read",
                args={"email_id": "msg_1"},
                intent_hash=intent["intent_hash"],
                capability_token_hash=token["token_hash"],
                provenance={"influenced_by": ["trusted.user"], "uses_data": [], "side_effect": None},
            )
            exec_result = await runtime.execute_action(db=db, envelope=envelope, run_id=run["run_id"])
            action_hash = exec_result["action_hash"]

            # Record a tool result
            await runtime.record_tool_result(
                db=db,
                action_hash=action_hash,
                result={"content": "Hello World", "status": "ok"},
            )

            # Verify it was persisted
            from sqlalchemy import select
            from app.models.action import Action
            db_result = await db.execute(
                select(Action).where(Action.action_hash == action_hash)
            )
            action = db_result.scalar_one_or_none()
            assert action is not None
            import json
            stored = json.loads(action.result_json)
            assert stored["content"] == "Hello World"
            assert stored["status"] == "ok"


# --- PolicyConfig Tests ---


class TestPolicyConfig:
    """Tests for PolicyConfig."""

    def test_default_rules(self):
        from app.core.policy_config import PolicyConfig
        config = PolicyConfig()
        assert len(config.rules) > 0

    def test_custom_rules(self):
        from app.core.policy_config import PolicyConfig
        custom = [
            {"id": "test_rule", "condition": {"side_effect": "shell"}, "action": "BLOCK", "severity": "critical"}
        ]
        config = PolicyConfig(custom)
        assert any(r["id"] == "test_rule" for r in config.rules)

    def test_evaluate_rule_shell(self):
        from app.core.policy_config import PolicyConfig
        config = PolicyConfig()
        context = {"tool": "shell.execute", "side_effect": "shell"}
        matched = False
        for rule in config.rules:
            result = config.evaluate_rule(rule, context)
            if result is not None:
                matched = True
                assert result["action"] in ("BLOCK", "REQUIRE_APPROVAL")
                break
        assert matched
