"""Generic Tool Registry for PACT.

Stores tool metadata and callables in a centralized registry.
Replaces the hardcoded _TOOLS dict in app/tools/__init__.py.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from app.core.tool_metadata import ToolMetadata, SideEffect


class ToolRegistry:
    """Centralized registry for PACT tools with metadata."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}

    def register_tool(
        self,
        tool_id: str,
        metadata: dict[str, Any],
        fn: Optional[Callable] = None,
    ) -> None:
        """Register a tool with metadata and optional callable.

        Args:
            tool_id: Unique tool identifier (e.g. 'email.send')
            metadata: Tool metadata dict (must include 'display_name')
            fn: Optional callable implementation
        """
        # Validate metadata through Pydantic model
        if isinstance(metadata, dict):
            meta = ToolMetadata(tool_id=tool_id, **metadata)
        elif isinstance(metadata, ToolMetadata):
            meta = metadata
        else:
            raise ValueError(f"metadata must be dict or ToolMetadata, got {type(metadata)}")

        self._tools[tool_id] = {
            "metadata": meta.model_dump(),
            "callable": fn,
        }

    def get_tool(self, tool_id: str) -> Optional[dict[str, Any]]:
        """Get tool info by ID.

        Returns:
            Dict with 'metadata' and 'callable' keys, or None if not found.
        """
        return self._tools.get(tool_id)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools with their metadata."""
        return [
            {"tool_id": tid, "metadata": info["metadata"]}
            for tid, info in self._tools.items()
        ]

    def get_callable(self, tool_id: str) -> Optional[Callable]:
        """Get the callable for a tool, or None if not registered / no callable."""
        tool = self._tools.get(tool_id)
        if tool:
            return tool.get("callable")
        return None

    def has_tool(self, tool_id: str) -> bool:
        """Check if a tool is registered."""
        return tool_id in self._tools

    def unregister_tool(self, tool_id: str) -> bool:
        """Remove a tool from the registry. Returns True if found."""
        if tool_id in self._tools:
            del self._tools[tool_id]
            return True
        return False


# Global default registry instance
_default_registry: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """Get or create the global default tool registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
        _register_default_tools(_default_registry)
    return _default_registry


def _register_default_tools(registry: ToolRegistry) -> None:
    """Register the built-in PACT demo tools."""
    from app.tools.email import email_read, email_send
    from app.tools.web import web_read
    from app.tools.file import file_read, file_read_secret
    from app.tools.shell import shell_execute_mock

    tools = [
        ("email.read", {
            "display_name": "Read Email",
            "description": "Read email content from inbox.",
            "side_effect": SideEffect.READ,
            "resource_type": "email_id",
            "output_provenance": ["untrusted.email"],
            "sensitivity": "medium",
        }, email_read),
        ("email.send", {
            "display_name": "Send Email",
            "description": "Send an email to an external recipient.",
            "side_effect": SideEffect.EXTERNAL_WRITE,
            "resource_type": "email_address",
            "resource_extractor": {"type": "json_path", "path": "$.to"},
            "output_provenance": ["external_write"],
            "sensitivity": "high",
            "default_requires_approval": True,
        }, email_send),
        ("web.read", {
            "display_name": "Read Web Page",
            "description": "Fetch and read web page content.",
            "side_effect": SideEffect.READ,
            "resource_type": "url",
            "output_provenance": ["untrusted.web"],
            "sensitivity": "medium",
        }, web_read),
        ("file.read", {
            "display_name": "Read File",
            "description": "Read file content from filesystem.",
            "side_effect": SideEffect.READ,
            "resource_type": "file_path",
            "output_provenance": ["internal.data"],
            "sensitivity": "low",
        }, file_read),
        ("file.read_secret", {
            "display_name": "Read Secret File",
            "description": "Read secret/sensitive file content.",
            "side_effect": SideEffect.READ,
            "resource_type": "file_path",
            "output_provenance": ["secret"],
            "sensitivity": "critical",
            "default_requires_approval": True,
        }, file_read_secret),
        ("shell.execute_mock", {
            "display_name": "Execute Shell Command",
            "description": "Execute a shell command (mock).",
            "side_effect": SideEffect.SHELL,
            "resource_type": "command",
            "output_provenance": ["external_write"],
            "sensitivity": "critical",
            "default_requires_approval": True,
        }, shell_execute_mock),
        ("respond_to_user", {
            "display_name": "Respond to User",
            "description": "Generate a response to the user.",
            "side_effect": SideEffect.NONE,
            "resource_type": "default",
            "output_provenance": ["agent.generated"],
            "sensitivity": "low",
        }, lambda message="", **kw: {"type": "response", "message": message}),
        ("summarize", {
            "display_name": "Summarize",
            "description": "Summarize text content.",
            "side_effect": SideEffect.NONE,
            "resource_type": "default",
            "output_provenance": ["agent.generated"],
            "sensitivity": "low",
        }, lambda text="", **kw: {"type": "summary", "text": f"Summary of: {text[:100]}"}),
    ]

    for tool_id, meta, fn in tools:
        registry.register_tool(tool_id, meta, fn)
