"""LangChain tool wrapper with PACT enforcement.

LangChain is an **optional** dependency — the adapter works even when
langchain is not installed.  Only importing this module will succeed;
calling the integration features requires langchain_core at runtime.
"""

from __future__ import annotations

from typing import Optional, Any, Callable


class PactLangChainTool:
    """Wraps a LangChain tool with PACT enforcement.

    Usage::

        from langchain.tools import tool
        from app.adapters.frameworks.langchain import PactLangChainTool

        @tool
        def search_db(query: str) -> str:
            return db.search(query)

        secure_tool = PactLangChainTool(
            tool=search_db,
            tool_id='db.search',
            side_effect='read',
            resource_extractor=lambda args: args.get('query', 'default'),
        )
    """

    def __init__(
        self,
        tool: Any,
        tool_id: str,
        side_effect: str = "none",
        resource_extractor: Optional[Callable] = None,
        description: str = "",
    ):
        self.tool = tool
        self.tool_id = tool_id
        self.side_effect = side_effect
        self.resource_extractor = resource_extractor or (lambda args: "default")
        self.description = description or getattr(tool, "description", "")

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    def _get_pact_context(self, config: Optional[Any] = None) -> Optional[dict]:
        """Retrieve PACT context from a LangChain ``RunnableConfig``.

        The context is expected under ``config["configurable"]["pact_context"]``.
        Returns ``None`` when no context is available.
        """
        if config is None:
            return None

        try:
            # config may be a dict or a RunnableConfig object
            configurable = (
                config.get("configurable") if isinstance(config, dict) else getattr(config, "configurable", None)
            )
            if configurable and isinstance(configurable, dict):
                return configurable.get("pact_context")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(self, input_data: Any, config: Optional[Any] = None) -> Any:
        """Execute tool through PACT gateway.

        If PACT context is available the call is evaluated by the gateway
        before the underlying tool runs.  Without context the tool is called
        directly (useful for local development / testing).
        """
        # Normalise input to a dict
        if isinstance(input_data, dict):
            args = input_data
        elif isinstance(input_data, str):
            args = {"input": input_data}
        else:
            args = {"input": str(input_data)}

        # Attempt to get PACT context
        pact_context = self._get_pact_context(config)

        if pact_context:
            runtime = pact_context["pact_runtime"]
            if "gateway_service" not in getattr(runtime, "__dict__", {}):
                result = await runtime.propose_action(
                    db=pact_context["db"],
                    run_id=pact_context["run_id"],
                    agent_id=pact_context["agent_id"],
                    agent_private_key=pact_context["agent_private_key"],
                    tool=self.tool_id,
                    args=args,
                    intent_hash=pact_context["intent_hash"],
                    capability_token_hash=pact_context.get("capability_token_hash", ""),
                    provenance={
                        "influenced_by": ["trusted.user"],
                        "uses_data": [],
                        "side_effect": self.side_effect,
                    },
                )

                if result["decision"] != "ALLOW":
                    return f"PACT BLOCKED: {result.get('reasons', ['Unknown'])}"
            else:
                async def invoke_registered_tool(**tool_args):
                    if hasattr(self.tool, "ainvoke"):
                        return await self.tool.ainvoke(tool_args)
                    if hasattr(self.tool, "invoke"):
                        return self.tool.invoke(tool_args)
                    if callable(self.tool):
                        return self.tool(**tool_args)
                    raise RuntimeError(f"Tool {self.tool!r} is not callable")

                runtime.register_tool(
                    self.tool_id,
                    {
                        "display_name": self.tool_id,
                        "description": self.description,
                        "side_effect": self.side_effect,
                        "resource_type": "default",
                        "output_provenance": ["agent.generated"],
                    },
                    fn=invoke_registered_tool,
                )

                result = await runtime.execute_tool(
                    db=pact_context["db"],
                    run_id=pact_context["run_id"],
                    agent_id=pact_context["agent_id"],
                    agent_private_key=pact_context["agent_private_key"],
                    tool=self.tool_id,
                    args=args,
                    intent_hash=pact_context["intent_hash"],
                    capability_token_hash=pact_context.get("capability_token_hash", ""),
                )

                if result["decision"] != "ALLOW":
                    return f"PACT BLOCKED: {result.get('reasons', ['Unknown'])}"
                return result["tool_result"]

        # Execute underlying tool
        if hasattr(self.tool, "ainvoke"):
            return await self.tool.ainvoke(args)
        if hasattr(self.tool, "invoke"):
            return self.tool.invoke(args)
        if callable(self.tool):
            return self.tool(**args)
        raise RuntimeError(f"Tool {self.tool!r} is not callable")
