"""Centralized resource extraction and scope matching for tool args."""

from __future__ import annotations

import fnmatch
from urllib.parse import urlparse


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


def _email_in_scope(address: str, patterns: list[str]) -> bool:
    address = (address or "").strip().lower()
    for pat in patterns:
        pat = pat.strip().lower()
        if pat == "*":
            return True
        if pat.startswith("*@"):
            domain = pat[2:]
            if "@" in address and address.split("@", 1)[1] == domain:
                return True
        elif pat == address:
            return True
    return False


def _url_in_scope(url: str, patterns: list[str]) -> bool:
    parsed = urlparse(url if "://" in (url or "") else f"https://{url}")
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    for pat in patterns:
        pat = pat.strip().lower()
        if pat == "*":
            return True
        if pat.startswith("*."):
            suffix = pat[1:]  # ".domain.com"
            if host == pat[2:] or host.endswith(suffix):
                return True
        elif pat == host:
            return True
    return False


def resource_in_scope(resource_type: str, resource: str, scope: dict) -> bool:
    """Return True iff `resource` is within the authorized `scope` for its type.

    The scope is an operator-authorized allowlist of the form
    ``{resource_type: [patterns]}``. This is the authority boundary: the agent
    proposes a resource (via tool args) but may only act on resources the
    operator has granted. Default-deny — an absent or empty pattern list for a
    scoped resource type denies the action. Tools with no meaningful resource
    (resource_type "default") are always in scope.
    """
    if resource_type in ("default", "", None):
        return True

    patterns = scope.get(resource_type, []) if scope else []
    if not patterns:
        return False
    if "*" in patterns:
        return True

    if resource_type == "email_address":
        return _email_in_scope(resource, patterns)
    if resource_type == "url":
        return _url_in_scope(resource, patterns)

    # file_path, command, and any other string resource: glob match.
    resource = resource or ""
    return any(fnmatch.fnmatch(resource, pat) for pat in patterns)
