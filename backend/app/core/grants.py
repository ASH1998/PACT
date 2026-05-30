"""Operator grants — the authority ceiling for an agent/session.

A Grant is operator-controlled configuration (not agent-controlled) that bounds
what an agent may ever do, independent of what its task intent requests:

  * ``tools``          — the hard ceiling of tools the agent may use ("*" = all
                         registered tools). The per-task intent is the
                         intersection of the goal classifier and this ceiling.
  * ``resource_scope`` — the sole authority for *which resources* each tool may
                         touch, as an allowlist of patterns per resource_type
                         (see ``app.tools.resource.resource_in_scope``).

The built-in DEFAULT_GRANT is deny-by-default for external sinks: no outbound
email recipients and no shell commands are authorized until an operator supplies
a ``--grant`` file that explicitly widens the scope. This is what makes
exfiltration structurally impossible out of the box — the recipient/host/path is
checked against an allowlist the agent cannot widen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml
from pydantic import BaseModel, Field


class Grant(BaseModel):
    """An operator-authorized ceiling on tools and resource scopes."""

    tools: Union[list[str], str] = "*"
    resource_scope: dict[str, list[str]] = Field(default_factory=dict)

    def allows_tool(self, tool: str) -> bool:
        return self.tools == "*" or tool in self.tools

    def tool_ceiling(self, all_tools: list[str]) -> list[str]:
        """The set of tools this grant permits, given the registered universe."""
        if self.tools == "*":
            return list(all_tools)
        return [t for t in all_tools if t in self.tools]


# Deny-by-default. Out of the box only read/internal tools are authorized, and
# no external sinks: sending email, reading secrets, and running shell commands
# all require an explicit operator grant (see examples/grant.acme.yaml). This is
# what makes exfiltration structurally impossible by default — not a blocklist.
DEFAULT_GRANT = Grant(
    tools=[
        "file.read",
        "web.read",
        "email.read",
        "summarize",
        "respond_to_user",
    ],
    resource_scope={
        "email_address": [],   # moot unless operator also grants email.send
        "email_id": ["*"],     # reading the local inbox fixture is fine
        "file_path": ["*"],    # repo-relative; traversal blocked by the tool layer
        "url": ["*"],          # web reads allowed; enterprises typically restrict
        "command": [],         # moot unless operator also grants shell.execute_mock
    },
)


def load_grant(path: Union[str, Path]) -> Grant:
    """Load an operator grant from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return Grant(**data)
