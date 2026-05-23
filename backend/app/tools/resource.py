"""Centralized resource extraction from tool args."""


def resource_from_args(tool: str, args: dict) -> str:
    """Extract the resource identifier from tool args based on tool type."""
    if tool.startswith("email."):
        return args.get("email_id", args.get("to", "default"))
    elif tool.startswith("file."):
        return args.get("path", "default")
    elif tool.startswith("web."):
        return args.get("url", "default")
    elif tool.startswith("shell."):
        return args.get("command", "default")
    else:
        return "default"
