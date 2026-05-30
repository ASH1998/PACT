"""Tests for framework adapters (direct, LangChain, LangGraph)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.adapters.frameworks.direct import pact_tool
from app.adapters.frameworks.langchain import PactLangChainTool
from app.adapters.frameworks.langgraph import PactLangGraphNode


# ──────────────────────────────────────────────────────────────────────
# pact_tool decorator
# ──────────────────────────────────────────────────────────────────────


class TestPactToolDecorator:
    """Tests for the @pact_tool decorator."""

    def test_metadata_is_set(self):
        """Decorator attaches PACT metadata to the wrapper."""

        @pact_tool(
            tool_id="crm.update",
            side_effect="internal_write",
            resource_arg="contact_id",
            description="Update CRM contact",
            input_schema={"contact_id": "str", "fields": "dict"},
        )
        async def update_contact(contact_id: str, fields: dict):
            return {"ok": True}

        assert update_contact._pact_tool_id == "crm.update"
        assert update_contact._pact_side_effect == "internal_write"
        assert update_contact._pact_resource_arg == "contact_id"
        assert update_contact._pact_description == "Update CRM contact"
        assert update_contact._pact_input_schema == {
            "contact_id": "str",
            "fields": "dict",
        }

    async def test_raises_without_context(self):
        """Calling without pact_context raises ValueError."""

        @pact_tool(tool_id="test.tool")
        async def my_tool(x: int):
            return x

        with pytest.raises(ValueError, match="pact_context required"):
            await my_tool(42)

    async def test_allow_calls_function(self):
        """When runtime returns ALLOW the underlying function executes."""

        @pact_tool(tool_id="math.add", side_effect="none")
        async def add(a: int, b: int):
            return a + b

        mock_runtime = AsyncMock()
        mock_runtime.propose_action.return_value = {
            "decision": "ALLOW",
            "action_hash": "abc123",
        }

        ctx = {
            "db": MagicMock(),
            "run_id": "run_1",
            "agent_id": "agent_1",
            "agent_private_key": "key",
            "intent_hash": "ih",
            "capability_token_hash": "",
            "pact_runtime": mock_runtime,
        }

        result = await add(3, 5, pact_context=ctx)

        assert result["decision"] == "ALLOW"
        assert result["result"] == 8
        assert result["action_hash"] == "abc123"
        mock_runtime.propose_action.assert_awaited_once()

    async def test_block_returns_block(self):
        """When runtime returns BLOCK the function is NOT called."""

        call_count = 0

        @pact_tool(tool_id="dangerous.wipe")
        async def wipe():
            nonlocal call_count
            call_count += 1
            return "deleted"

        mock_runtime = AsyncMock()
        mock_runtime.propose_action.return_value = {
            "decision": "BLOCK",
            "action_hash": "h1",
            "reasons": ["Forbidden by policy"],
        }

        ctx = {
            "db": MagicMock(),
            "run_id": "run_1",
            "agent_id": "a1",
            "agent_private_key": "k",
            "intent_hash": "ih",
            "pact_runtime": mock_runtime,
        }

        result = await wipe(pact_context=ctx)

        assert result["decision"] == "BLOCK"
        assert "Forbidden by policy" in result["reasons"]
        assert call_count == 0  # function was NOT called

    async def test_require_approval_returns_approval_info(self):
        """When runtime returns REQUIRE_APPROVAL, approval_id is passed through."""

        @pact_tool(tool_id="shell.run", side_effect="external_write")
        async def run_cmd(cmd: str):
            return f"executed {cmd}"

        mock_runtime = AsyncMock()
        mock_runtime.propose_action.return_value = {
            "decision": "REQUIRE_APPROVAL",
            "action_hash": "h2",
            "approval_id": "appr_123",
        }

        ctx = {
            "db": MagicMock(),
            "run_id": "run_1",
            "agent_id": "a1",
            "agent_private_key": "k",
            "intent_hash": "ih",
            "pact_runtime": mock_runtime,
        }

        result = await run_cmd("ls -la", pact_context=ctx)

        assert result["decision"] == "REQUIRE_APPROVAL"
        assert result["approval_id"] == "appr_123"
        assert result["action_hash"] == "h2"

    async def test_resource_extraction(self):
        """resource_arg is extracted from kwargs and passed to runtime."""

        @pact_tool(tool_id="db.read", resource_arg="table")
        async def read_table(table: str):
            return []

        mock_runtime = AsyncMock()
        mock_runtime.propose_action.return_value = {
            "decision": "ALLOW",
            "action_hash": "h3",
        }

        ctx = {
            "db": MagicMock(),
            "run_id": "r",
            "agent_id": "a",
            "agent_private_key": "k",
            "intent_hash": "ih",
            "pact_runtime": mock_runtime,
        }

        await read_table(table="users", pact_context=ctx)

        # Verify propose_action was called with tool="db.read"
        call_kwargs = mock_runtime.propose_action.call_args
        assert call_kwargs.kwargs["tool"] == "db.read"


# ──────────────────────────────────────────────────────────────────────
# PactLangChainTool
# ──────────────────────────────────────────────────────────────────────


class TestPactLangChainTool:
    """Tests for PactLangChainTool wrapper."""

    def test_initialization(self):
        """PactLangChainTool stores all config correctly."""
        mock_tool = MagicMock()
        mock_tool.description = "Search the database"

        wrapper = PactLangChainTool(
            tool=mock_tool,
            tool_id="db.search",
            side_effect="read",
            resource_extractor=lambda args: args.get("query", "default"),
            description="Custom desc",
        )

        assert wrapper.tool is mock_tool
        assert wrapper.tool_id == "db.search"
        assert wrapper.side_effect == "read"
        assert wrapper.description == "Custom desc"

    def test_default_description_from_tool(self):
        """Falls back to tool.description when no explicit description given."""
        mock_tool = MagicMock()
        mock_tool.description = "Original desc"

        wrapper = PactLangChainTool(tool=mock_tool, tool_id="t")
        assert wrapper.description == "Original desc"

    async def test_run_without_context_executes_directly(self):
        """Without PACT context the underlying tool is called directly."""
        mock_tool = MagicMock(spec=["invoke"])
        mock_tool.invoke.return_value = "search results"

        wrapper = PactLangChainTool(tool=mock_tool, tool_id="db.search")

        result = await wrapper.run({"query": "hello"})
        assert result == "search results"
        mock_tool.invoke.assert_called_once_with({"query": "hello"})

    async def test_run_blocks_when_pact_blocks(self):
        """With PACT context, blocks return a blocked message."""
        mock_tool = MagicMock(spec=["invoke"])
        wrapper = PactLangChainTool(
            tool=mock_tool,
            tool_id="dangerous.nuke",
            side_effect="external_write",
        )

        mock_runtime = AsyncMock()
        mock_runtime.propose_action.return_value = {
            "decision": "BLOCK",
            "reasons": ["Too dangerous"],
            "action_hash": "h",
        }

        pact_ctx = {
            "db": MagicMock(),
            "run_id": "r",
            "agent_id": "a",
            "agent_private_key": "k",
            "intent_hash": "ih",
            "pact_runtime": mock_runtime,
        }

        result = await wrapper.run(
            {"cmd": "rm -rf /"},
            config={"configurable": {"pact_context": pact_ctx}},
        )

        assert "PACT BLOCKED" in result
        mock_tool.invoke.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# PactLangGraphNode
# ──────────────────────────────────────────────────────────────────────


class TestPactLangGraphNode:
    """Tests for PactLangGraphNode middleware."""

    def test_initialization(self):
        """Node stores config correctly."""
        async def my_fn(state):
            return state

        node = PactLangGraphNode(
            node_fn=my_fn,
            tool_id="db.write",
            side_effect="internal_write",
        )

        assert node.tool_id == "db.write"
        assert node.side_effect == "internal_write"

    async def test_calls_node_fn_without_context(self):
        """Without _pact_context the underlying node function is called."""

        async def my_fn(state):
            return {"result": "ok"}

        node = PactLangGraphNode(node_fn=my_fn, tool_id="t")

        result = await node({"key": "value"})
        assert result == {"result": "ok"}

    async def test_blocks_when_pact_blocks(self):
        """With _pact_context, a BLOCK decision prevents node execution."""

        call_count = 0

        async def my_fn(state):
            nonlocal call_count
            call_count += 1
            return {"executed": True}

        node = PactLangGraphNode(
            node_fn=my_fn,
            tool_id="dangerous.op",
            side_effect="external_write",
        )

        mock_runtime = AsyncMock()
        mock_runtime.propose_action.return_value = {
            "decision": "BLOCK",
            "reasons": ["Not allowed"],
            "action_hash": "h",
        }

        state = {
            "_pact_context": {
                "db": MagicMock(),
                "run_id": "r",
                "agent_id": "a",
                "agent_private_key": "k",
                "intent_hash": "ih",
                "pact_runtime": mock_runtime,
            },
            "tool_args": {"x": 1},
        }

        result = await node(state)

        assert "PACT BLOCKED" in result.get("error", "")
        assert call_count == 0

    async def test_allows_and_calls_node(self):
        """With ALLOW decision the node function executes normally."""

        async def my_fn(state):
            return {"result": "computed"}

        node = PactLangGraphNode(node_fn=my_fn, tool_id="db.read")

        mock_runtime = AsyncMock()
        mock_runtime.propose_action.return_value = {
            "decision": "ALLOW",
            "action_hash": "h",
        }

        state = {
            "_pact_context": {
                "db": MagicMock(),
                "run_id": "r",
                "agent_id": "a",
                "agent_private_key": "k",
                "intent_hash": "ih",
                "pact_runtime": mock_runtime,
            },
            "tool_args": {},
        }

        result = await node(state)
        assert result == {"result": "computed"}
