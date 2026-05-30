"""Direct Python tool wrapper for PACT enforcement — no framework dependency."""

from __future__ import annotations

import functools
import inspect
from typing import Callable, Optional


def pact_tool(
    tool_id: str,
    side_effect: str = "none",
    resource_arg: Optional[str] = None,
    description: str = "",
    input_schema: Optional[dict] = None,
):
    """Decorator that wraps a function with PACT gateway enforcement.

    Usage::

        @pact_tool(tool_id='crm.update_contact', side_effect='internal_write',
                   resource_arg='contact_id')
        async def update_contact(contact_id: str, fields: dict):
            return await db.update(contact_id, fields)

    The decorated function **must** be called with a ``pact_context`` kwarg
    containing::

        {
            'run_id': str,
            'agent_id': str,
            'agent_private_key': str,
            'intent_hash': str,
            'capability_token_hash': str,   # optional
            'pact_runtime': RuntimeService,
            'db': AsyncSession,
        }
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, pact_context: Optional[dict] = None, **kwargs):
            if pact_context is None:
                raise ValueError(
                    f"pact_context required for PACT-wrapped tool {tool_id}"
                )

            runtime = pact_context["pact_runtime"]
            if "gateway_service" in getattr(runtime, "__dict__", {}):
                runtime.register_tool(
                    tool_id,
                    {
                        "display_name": tool_id,
                        "description": description,
                        "side_effect": side_effect,
                        "resource_type": resource_arg or "default",
                        "input_schema": input_schema or {},
                        "output_provenance": ["agent.generated"],
                    },
                    fn=fn,
                )

                result = await runtime.execute_tool(
                    db=pact_context["db"],
                    run_id=pact_context["run_id"],
                    agent_id=pact_context["agent_id"],
                    agent_private_key=pact_context["agent_private_key"],
                    tool=tool_id,
                    args=kwargs,
                    intent_hash=pact_context["intent_hash"],
                    capability_token_hash=pact_context.get("capability_token_hash", ""),
                )
            else:
                result = await runtime.propose_action(
                    db=pact_context["db"],
                    run_id=pact_context["run_id"],
                    agent_id=pact_context["agent_id"],
                    agent_private_key=pact_context["agent_private_key"],
                    tool=tool_id,
                    args=kwargs,
                    intent_hash=pact_context["intent_hash"],
                    capability_token_hash=pact_context.get("capability_token_hash", ""),
                    provenance={
                        "influenced_by": ["trusted.user"],
                        "uses_data": [],
                        "side_effect": side_effect,
                    },
                )

            if result["decision"] == "ALLOW":
                tool_result = result.get("tool_result")
                if tool_result is None:
                    tool_result = fn(*args, **kwargs)
                    if inspect.isawaitable(tool_result):
                        tool_result = await tool_result
                return {
                    "decision": "ALLOW",
                    "result": tool_result,
                    "action_hash": result["action_hash"],
                }
            elif result["decision"] == "REQUIRE_APPROVAL":
                return {
                    "decision": "REQUIRE_APPROVAL",
                    "approval_id": result.get("approval_id"),
                    "action_hash": result["action_hash"],
                }
            else:
                return {
                    "decision": "BLOCK",
                    "reasons": result.get("reasons", []),
                    "action_hash": result["action_hash"],
                }

        # Attach PACT metadata for introspection
        wrapper._pact_tool_id = tool_id
        wrapper._pact_side_effect = side_effect
        wrapper._pact_resource_arg = resource_arg
        wrapper._pact_description = description
        wrapper._pact_input_schema = input_schema
        return wrapper

    return decorator
