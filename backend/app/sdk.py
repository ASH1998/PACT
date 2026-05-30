"""Public library-call SDK for integrating external agents with PACT.

The SDK keeps application code on the production gateway path: every tool call
is signed, policy checked, written to the ledger, and only then executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.factory import get_runtime
from app.core.runtime import PactRuntime
from app.core.tool_metadata import SideEffect


def _side_effect_value(side_effect: SideEffect | str) -> str:
    if isinstance(side_effect, SideEffect):
        return side_effect.value
    return side_effect


@dataclass(slots=True)
class ToolSpec:
    """Tool definition used by library integrations."""

    tool_id: str
    fn: Optional[Callable[..., Any]] = None
    display_name: str = ""
    description: str = ""
    side_effect: SideEffect | str = SideEffect.NONE
    resource_type: str = "default"
    output_provenance: list[str] = field(default_factory=list)
    sensitivity: str = "low"
    requires_approval: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"

    def metadata(self) -> dict[str, Any]:
        """Return registry metadata for this tool."""
        return {
            "display_name": self.display_name or self.tool_id,
            "version": self.version,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "side_effect": _side_effect_value(self.side_effect),
            "resource_type": self.resource_type,
            "output_provenance": self.output_provenance,
            "sensitivity": self.sensitivity,
            "default_requires_approval": self.requires_approval,
        }


class PactAgentSession:
    """A single agent run with intent-bound capabilities."""

    def __init__(
        self,
        *,
        runtime: PactRuntime,
        db: AsyncSession,
        run_id: str,
        agent_id: str,
        agent_private_key: str,
        intent_hash: str,
        capability_tokens: dict[str, str],
    ) -> None:
        self.runtime = runtime
        self.db = db
        self.run_id = run_id
        self.agent_id = agent_id
        self.agent_private_key = agent_private_key
        self.intent_hash = intent_hash
        self.capability_tokens = capability_tokens

    def context_for(self, tool_id: str) -> dict[str, Any]:
        """Return a framework-adapter context for a specific tool."""
        return {
            "pact_runtime": self.runtime,
            "db": self.db,
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "agent_private_key": self.agent_private_key,
            "intent_hash": self.intent_hash,
            "capability_token_hash": self.capability_tokens.get(tool_id, ""),
        }

    async def call(
        self,
        tool_id: str,
        args: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute a tool through the full PACT gateway path."""
        return await self.runtime.execute_tool(
            db=self.db,
            run_id=self.run_id,
            agent_id=self.agent_id,
            agent_private_key=self.agent_private_key,
            tool=tool_id,
            args=args or {},
            intent_hash=self.intent_hash,
            capability_token_hash=self.capability_tokens.get(tool_id, ""),
        )

    async def evaluate(
        self,
        tool_id: str,
        args: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Evaluate a tool call without ledger, token, or tool side effects."""
        return await self.runtime.evaluate_action(
            db=self.db,
            run_id=self.run_id,
            agent_id=self.agent_id,
            tool=tool_id,
            args=args or {},
            intent_hash=self.intent_hash,
            capability_token_hash=self.capability_tokens.get(tool_id, ""),
            agent_private_key=self.agent_private_key,
        )

    async def verify_ledger(self) -> dict[str, Any]:
        """Verify the hash-chain ledger for this run."""
        return await self.runtime.verify_run(self.db, self.run_id)


class Pact:
    """High-level PACT integration facade for agent runtimes."""

    def __init__(self, runtime: Optional[PactRuntime] = None) -> None:
        self.runtime = runtime or get_runtime()

    def register_tool(self, spec: ToolSpec) -> None:
        """Register a tool globally with the runtime."""
        self.runtime.register_tool(spec.tool_id, spec.metadata(), fn=spec.fn)

    async def start_session(
        self,
        *,
        db: AsyncSession,
        agent_id: str,
        user_goal: str,
        tools: list[ToolSpec],
        owner: str = "app",
        agent_type: str = "agent",
        allowed_tools: Optional[list[str]] = None,
        forbidden_tools: Optional[list[str]] = None,
        agent_private_key: Optional[str] = None,
        capability_ttl_seconds: int = 300,
        capability_max_uses: int = 10,
    ) -> PactAgentSession:
        """Create a run, intent, and capabilities for a tool-using agent.

        Existing agents can pass their stored ``agent_private_key``.  New demo
        or ephemeral agents can omit it and PACT will register an agent passport
        and return a session containing the generated private key.
        """
        for spec in tools:
            self.register_tool(spec)

        existing_passport = await self.runtime.passport_service.get_passport(db, agent_id)
        if existing_passport and not agent_private_key:
            raise ValueError(
                f"Agent {agent_id!r} already exists; pass its stored agent_private_key"
            )
        if not existing_passport and agent_private_key:
            raise ValueError(
                f"Agent {agent_id!r} is not registered; omit agent_private_key to create it"
            )
        if not existing_passport:
            registration = await self.runtime.register_agent(
                db=db,
                agent_id=agent_id,
                owner=owner,
                agent_type=agent_type,
                allowed_domains=["*"],
            )
            agent_private_key = registration["agent_private_key"]

        assert agent_private_key is not None

        allowed = allowed_tools if allowed_tools is not None else [spec.tool_id for spec in tools]
        forbidden = forbidden_tools or []

        intent = await self.runtime.create_intent(
            db=db,
            user_goal=user_goal,
            created_by=agent_id,
            allowed_actions=allowed,
            forbidden_actions=forbidden,
        )
        run = await self.runtime.create_run(
            db=db,
            agent_id=agent_id,
            scenario_name="library_integration",
            user_goal=user_goal,
        )

        capability_tokens: dict[str, str] = {}
        for tool_id in allowed:
            token = await self.runtime.issue_capability(
                db=db,
                agent_id=agent_id,
                intent_hash=intent["intent_hash"],
                capability=tool_id,
                resource="default",
                max_uses=capability_max_uses,
                ttl_seconds=capability_ttl_seconds,
            )
            capability_tokens[tool_id] = token["token_hash"]

        return PactAgentSession(
            runtime=self.runtime,
            db=db,
            run_id=run["run_id"],
            agent_id=agent_id,
            agent_private_key=agent_private_key,
            intent_hash=intent["intent_hash"],
            capability_tokens=capability_tokens,
        )


__all__ = ["Pact", "PactAgentSession", "ToolSpec"]
