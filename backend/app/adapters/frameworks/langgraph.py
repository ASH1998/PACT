"""LangGraph middleware for PACT enforcement.

LangGraph is an **optional** dependency — this module can be imported
even when langgraph / langchain are not installed.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


class PactLangGraphNode:
    """Middleware for LangGraph tool nodes.

    Wraps a tool-node function to enforce PACT before execution.

    Usage::

        async def my_tool_node(state):
            # actual tool logic
            return {"result": ...}

        secure_node = PactLangGraphNode(
            node_fn=my_tool_node,
            tool_id="db.write",
            side_effect="internal_write",
        )

        # In your LangGraph graph:
        graph.add_node("write_step", secure_node)
    """

    def __init__(
        self,
        node_fn: Callable,
        tool_id: str,
        side_effect: str = "none",
        resource_extractor: Optional[Callable] = None,
    ):
        self.node_fn = node_fn
        self.tool_id = tool_id
        self.side_effect = side_effect
        self.resource_extractor = resource_extractor or (lambda state: "default")

    async def __call__(self, state: dict, config: Any = None) -> dict:
        """Execute as a LangGraph node with PACT enforcement.

        Looks for ``state["_pact_context"]``.  When present the action is
        evaluated through the PACT runtime before the underlying node runs.
        """
        pact_context: Optional[dict] = state.get("_pact_context")

        if pact_context:
            runtime = pact_context["pact_runtime"]
            if "gateway_service" not in getattr(runtime, "__dict__", {}):
                result = await runtime.propose_action(
                    db=pact_context["db"],
                    run_id=pact_context["run_id"],
                    agent_id=pact_context["agent_id"],
                    agent_private_key=pact_context["agent_private_key"],
                    tool=self.tool_id,
                    args=state.get("tool_args", {}),
                    intent_hash=pact_context["intent_hash"],
                    capability_token_hash=pact_context.get("capability_token_hash", ""),
                    provenance={
                        "influenced_by": ["trusted.user"],
                        "uses_data": [],
                        "side_effect": self.side_effect,
                    },
                )

                if result["decision"] != "ALLOW":
                    return {
                        "error": f"PACT BLOCKED: {result.get('reasons', [])}",
                        "pact_decision": result["decision"],
                    }
                return await self.node_fn(state)

            async def invoke_node(**tool_args):
                next_state = dict(state)
                next_state["tool_args"] = tool_args
                return await self.node_fn(next_state)

            runtime.register_tool(
                self.tool_id,
                {
                    "display_name": self.tool_id,
                    "side_effect": self.side_effect,
                    "resource_type": "default",
                    "output_provenance": ["agent.generated"],
                },
                fn=invoke_node,
            )

            result = await runtime.execute_tool(
                db=pact_context["db"],
                run_id=pact_context["run_id"],
                agent_id=pact_context["agent_id"],
                agent_private_key=pact_context["agent_private_key"],
                tool=self.tool_id,
                args=state.get("tool_args", {}),
                intent_hash=pact_context["intent_hash"],
                capability_token_hash=pact_context.get("capability_token_hash", ""),
            )

            if result["decision"] != "ALLOW":
                return {
                    "error": f"PACT BLOCKED: {result.get('reasons', [])}",
                    "pact_decision": result["decision"],
                }
            return result["tool_result"]

        return await self.node_fn(state)
