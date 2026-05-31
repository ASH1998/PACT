#!/usr/bin/env python3
"""PACT PreToolUse hook for Claude Code.

Claude Code invokes this before every matched native tool call (Bash, Read,
Edit, Write, MultiEdit, WebFetch). The hook maps the native tool to a PACT tool,
runs it through the same signed-envelope gateway path as ``/pact check``, and
returns a permission decision:

  ALLOW            -> "allow"  (proceed, recorded in the dashboard)
  BLOCK            -> "deny"   (refused, recorded in the dashboard)
  REQUIRE_APPROVAL -> "ask"    (Claude Code prompts the user)

Design choices for a smooth demo:

* Fail OPEN. If there is no active PACT session, or the backend is down, or the
  tool does not map to a PACT capability, the hook stays silent (exit 0, no
  output) so Claude Code falls back to its normal permission flow. The plugin
  only enforces once the user runs ``/pact start``.
* The hook never intercepts the PACT plumbing itself (its own CLI / hook) to
  avoid recursion and dashboard noise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pact_cli  # noqa: E402  (local import after sys.path tweak)


SECRET_HINT = re.compile(
    r"(\.env|secret|credential|password|\.pem$|\.key$|id_rsa|token|apikey|api_key)",
    re.IGNORECASE,
)

# Bash command substrings that mean "this is PACT plumbing" -> never intercept.
SELF_MARKERS = ("pact_cli.py", "pact_hook.py", "plugins/pact-claude", "plugins/pact-codex")


def emit(decision: str, reason: str, context: str | None = None) -> None:
    out: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    if context:
        out["hookSpecificOutput"]["additionalContext"] = context
    print(json.dumps(out))
    raise SystemExit(0)


def defer() -> None:
    """Stay silent: let Claude Code use its normal permission flow."""
    raise SystemExit(0)


def map_tool(tool_name: str, tool_input: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Map a native Claude Code tool call to a (pact_tool, pact_args) pair."""
    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        if any(marker in command for marker in SELF_MARKERS):
            return None  # don't audit PACT's own plumbing
        return "shell.execute_mock", {"command": command}

    if tool_name in ("Read", "NotebookRead"):
        path = str(tool_input.get("file_path", ""))
        if not path:
            return None
        tool = "file.read_secret" if SECRET_HINT.search(path) else "file.read"
        return tool, {"path": path}

    if tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = str(tool_input.get("file_path") or tool_input.get("notebook_path", ""))
        if not path:
            return None
        return "file.write", {"path": path}

    if tool_name in ("WebFetch", "WebSearch"):
        url = str(tool_input.get("url") or tool_input.get("query", ""))
        if not url:
            return None
        return "web.read", {"url": url}

    return None


def main() -> None:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        defer()

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {}) or {}
    if not isinstance(tool_input, dict):
        defer()

    mapped = map_tool(tool_name, tool_input)
    if mapped is None:
        defer()
    pact_tool, pact_args = mapped

    # No active session -> plugin is dormant, don't get in the way.
    try:
        state = pact_cli.load_state(required=False)
    except Exception:
        defer()
    if not state:
        defer()

    # Run through the PACT gateway. Fail OPEN on any backend/transport error.
    try:
        decision = pact_cli.run_check(state, pact_tool, pact_args)
    except Exception as exc:  # pact_cli.PactError, network, etc.
        emit(
            "ask",
            f"PACT could not authorize this {tool_name} ({pact_tool}). Backend issue: {exc}",
        )

    verdict = decision.get("decision")
    reasons = decision.get("reasons") or decision.get("reason") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    reason_text = "; ".join(str(r) for r in reasons) if reasons else "no policy reasons returned"
    run_id = state.get("run_id", "?")
    action_hash = decision.get("action_hash", "?")
    context = (
        f"PACT run {run_id} recorded {tool_name} -> {pact_tool} "
        f"as {verdict} (action {action_hash}). Visible in the PACT dashboard."
    )

    if verdict == "ALLOW":
        emit("allow", f"PACT ALLOW [{pact_tool}]: {reason_text}", context)
    elif verdict == "REQUIRE_APPROVAL":
        emit("ask", f"PACT REQUIRE_APPROVAL [{pact_tool}]: {reason_text}", context)
    elif verdict == "BLOCK":
        emit("deny", f"PACT BLOCK [{pact_tool}]: {reason_text}", context)
    else:
        # Unknown verdict -> be safe, ask the user.
        emit("ask", f"PACT returned '{verdict}' [{pact_tool}]: {reason_text}", context)


if __name__ == "__main__":
    main()
