from __future__ import annotations
"""Mock tools for PACT demo. Simple, deterministic functions.

Now supports registration through the centralized ToolRegistry.
The hardcoded _TOOLS dict is kept for backward compatibility and
populated from the registry.
"""

from app.tools.email import email_read, email_send
from app.tools.web import web_read
from app.tools.file import file_read, file_read_secret
from app.tools.shell import shell_execute_mock


# Legacy tool registry (kept for backward compatibility with gateway.py)
# Populated from the centralized ToolRegistry on first access.
_TOOLS: dict[str, callable] = {
    "email.read": email_read,
    "email.send": email_send,
    "web.read": web_read,
    "file.read": file_read,
    "file.read_secret": file_read_secret,
    "shell.execute_mock": shell_execute_mock,
    "respond_to_user": lambda message="", **kw: {"type": "response", "message": message},
    "summarize": lambda text="", **kw: {"type": "summary", "text": f"Summary of: {text[:100]}"},
}


def get_mock_tool(tool_name: str) -> callable | None:
    """Get a mock tool function by name.

    First checks the legacy _TOOLS dict (for backward compat),
    then falls back to the centralized registry.
    """
    tool = _TOOLS.get(tool_name)
    if tool:
        return tool
    # Fall back to centralized registry
    try:
        from app.core.registry import get_default_registry
        registry = get_default_registry()
        return registry.get_callable(tool_name)
    except ImportError:
        return None


def list_tools() -> list[str]:
    """List all available mock tools."""
    # Combine both sources
    tool_names = set(_TOOLS.keys())
    try:
        from app.core.registry import get_default_registry
        registry = get_default_registry()
        for entry in registry.list_tools():
            tool_names.add(entry["tool_id"])
    except ImportError:
        pass
    return list(tool_names)
