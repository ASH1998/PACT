"""Abstract interfaces for PACT core components.

These are reference interfaces — existing concrete implementations
(PassportService, IntentService, etc.) continue to work as-is.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class StorageInterface(ABC):
    """Abstract interface for PACT data storage."""

    @abstractmethod
    async def get(self, key: str) -> Optional[dict]:
        """Retrieve an entity by key."""
        ...

    @abstractmethod
    async def put(self, key: str, value: dict) -> None:
        """Store an entity."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete an entity by key."""
        ...

    @abstractmethod
    async def query(self, prefix: str) -> list[dict]:
        """Query entities by key prefix."""
        ...


class PolicyInterface(ABC):
    """Abstract interface for policy evaluation."""

    @abstractmethod
    def evaluate(
        self,
        tool: str,
        allowed_actions: list[str],
        forbidden_actions: list[str],
        provenance: dict,
        **kwargs: Any,
    ) -> Any:
        """Evaluate an action against policy rules and return a decision."""
        ...


class ToolRegistryInterface(ABC):
    """Abstract interface for tool registry."""

    @abstractmethod
    def register_tool(self, tool_id: str, metadata: dict, fn: Any = None) -> None:
        """Register a tool with metadata and optional callable."""
        ...

    @abstractmethod
    def get_tool(self, tool_id: str) -> Optional[dict]:
        """Get tool info by ID. Returns {metadata, callable} or None."""
        ...

    @abstractmethod
    def list_tools(self) -> list[dict]:
        """List all registered tools."""
        ...
