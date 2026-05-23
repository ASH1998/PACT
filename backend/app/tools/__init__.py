from __future__ import annotations
"""Mock tools for PACT demo. Simple, deterministic functions."""

from app.tools.email import email_read, email_send
from app.tools.web import web_read
from app.tools.file import file_read, file_read_secret
from app.tools.shell import shell_execute_mock
from app.tools.seed_data import SEED_DATA

# Tool registry
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
    """Get a mock tool function by name."""
    return _TOOLS.get(tool_name)


def list_tools() -> list[str]:
    """List all available mock tools."""
    return list(_TOOLS.keys())
