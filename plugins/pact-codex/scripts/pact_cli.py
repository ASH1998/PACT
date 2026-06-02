#!/usr/bin/env python3
"""PACT CLI for the Codex plugin.

This script gives Codex a slash-command style interface:

  /pact start   -> create an audited PACT run
  /pact check   -> authorize a proposed action before native tool use
  /pact attach  -> attach an execution result for dashboard replay
  /pact status  -> inspect current session and ledger status
  /pact replay  -> summarize recorded run steps

It intentionally uses the existing PACT v1 REST API instead of adding a new
backend surface.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_GRANT_PATH = PLUGIN_ROOT / "assets" / "default-grant.yaml"
STATE_PATH = REPO_ROOT / ".pact" / "codex-session.json"


def _venv_candidates() -> list[Path]:
    """Candidate virtualenv interpreters, most-preferred first.

    Covers both interpreter layouts -- Windows (``Scripts/python.exe``) and POSIX
    (``bin/python``) -- and both common locations: the repo root ``.venv`` and the
    ``backend/.venv`` provisioned by ``uv``.
    """
    if os.name == "nt":
        rel = Path("Scripts") / "python.exe"
    else:
        rel = Path("bin") / "python"
    roots = [REPO_ROOT / ".venv", REPO_ROOT / "backend" / ".venv"]
    return [root / rel for root in roots]


def venv_python() -> Path | None:
    """Best virtualenv interpreter for signing PACT envelopes.

    Returns the first candidate that can ``import nacl`` (PyNaCl), so signing
    works regardless of which env the user provisioned. Falls back to the first
    interpreter that merely exists so error messages can show a real path.
    Returns ``None`` if no virtualenv interpreter is present.
    """
    import subprocess

    existing = [p for p in _venv_candidates() if p.exists()]
    for python in existing:
        try:
            probe = subprocess.run(
                [str(python), "-c", "import nacl"],
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return python
    return existing[0] if existing else None

TOOL_METADATA: dict[str, dict[str, Any]] = {
    "email.read": {
        "name": "Read Email",
        "description": "Read configured local email data.",
        "side_effect": "read",
        "resource_type": "email_id",
        "sensitivity": "medium",
        "requires_approval": False,
    },
    "email.send": {
        "name": "Send Email",
        "description": "Send email through configured SMTP.",
        "side_effect": "external_write",
        "resource_type": "email_address",
        "sensitivity": "high",
        "requires_approval": False,
    },
    "web.read": {
        "name": "Read Web Page",
        "description": "Fetch a web page.",
        "side_effect": "read",
        "resource_type": "url",
        "sensitivity": "medium",
        "requires_approval": False,
    },
    "file.read": {
        "name": "Read File",
        "description": "Read a local non-secret file.",
        "side_effect": "read",
        "resource_type": "file_path",
        "sensitivity": "low",
        "requires_approval": False,
    },
    "file.read_secret": {
        "name": "Read Secret File",
        "description": "Read a local secret file with redaction.",
        "side_effect": "read",
        "resource_type": "file_path",
        "sensitivity": "critical",
        "requires_approval": True,
    },
    "shell.execute_mock": {
        "name": "Execute Shell Command",
        "description": "Execute a local shell command after PACT approval.",
        "side_effect": "shell",
        "resource_type": "command",
        "sensitivity": "critical",
        "requires_approval": True,
    },
    "summarize": {
        "name": "Summarize Text",
        "description": "Create a short summary.",
        "side_effect": "none",
        "resource_type": "default",
        "sensitivity": "low",
        "requires_approval": False,
    },
    "respond_to_user": {
        "name": "Respond To User",
        "description": "Return a response to the user.",
        "side_effect": "none",
        "resource_type": "default",
        "sensitivity": "low",
        "requires_approval": False,
    },
}

ALL_TOOLS = list(TOOL_METADATA)


class PactError(RuntimeError):
    """Expected CLI error with JSON output."""


def json_out(payload: dict[str, Any], status: int = 0) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(status)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def hash_payload(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def sign_envelope(envelope: dict[str, Any], private_key_b64: str) -> None:
    try:
        from nacl.signing import SigningKey
    except ImportError as exc:
        vpy = venv_python()
        if vpy and os.environ.get("PACT_CODEX_REEXECED") != "1":
            import subprocess

            env = os.environ.copy()
            env["PACT_CODEX_REEXECED"] = "1"
            # Re-run under the venv interpreter (which has PyNaCl). subprocess.run
            # behaves identically on POSIX and Windows -- os.execve does not: on
            # Windows it detaches and loses stdout -- and propagates the exit code.
            completed = subprocess.run([str(vpy), *sys.argv], env=env)
            raise SystemExit(completed.returncode)
        raise PactError(
            "PyNaCl is required to sign PACT envelopes. Run through the backend "
            "environment: uv run --project backend --active python "
            "plugins/pact-codex/scripts/pact_cli.py ..."
        ) from exc

    seed = base64.b64decode(private_key_b64)
    payload = dict(envelope)
    payload.pop("agent_signature", None)
    signature = SigningKey(seed).sign(canonical_json(payload)).signature
    envelope["agent_signature"] = base64.b64encode(signature).decode()


def request_json(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    base_url = os.environ.get("PACT_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise PactError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise PactError(
            f"PACT backend is unavailable at {base_url}. Start it with: "
            "uv run --project backend --active uvicorn app.main:app "
            "--app-dir backend --reload --port 8000"
        ) from exc
    if not raw:
        return {}
    return json.loads(raw.decode())


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        raise PactError("No PACT Codex session exists. Run /pact start first.")
    return json.loads(STATE_PATH.read_text())


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    try:
        os.chmod(STATE_PATH, 0o600)
    except OSError:
        pass


def parse_scalar(raw: str) -> str:
    value = raw.split("#", 1)[0].strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return value


def parse_grant(path: Path) -> dict[str, Any]:
    try:
        import yaml

        data = yaml.safe_load(path.read_text()) or {}
        tools = data.get("tools", [])
        scope = data.get("resource_scope", {}) or {}
        if tools == "*":
            return {"tools": "*", "resource_scope": scope}
        return {"tools": list(tools or []), "resource_scope": scope}
    except ImportError:
        pass

    # Minimal YAML parser for the simple grant shape used by this plugin.
    tools: str | list[str] = []
    scope: dict[str, list[str]] = {}
    section: str | None = None
    current_scope_key: str | None = None
    for line in path.read_text().splitlines():
        stripped = line.split("#", 1)[0].rstrip()
        if not stripped:
            continue
        if not line.startswith(" "):
            key, _, raw_value = stripped.partition(":")
            section = key.strip()
            current_scope_key = None
            value = parse_scalar(raw_value)
            if section == "tools" and value == "*":
                tools = "*"
            continue
        if section == "tools" and stripped.lstrip().startswith("- "):
            if not isinstance(tools, list):
                tools = []
            tools.append(parse_scalar(stripped.lstrip()[2:]))
        elif section == "resource_scope":
            indent = len(line) - len(line.lstrip(" "))
            if indent == 2 and stripped.endswith(":"):
                current_scope_key = stripped.strip()[:-1]
                scope[current_scope_key] = []
            elif indent >= 4 and current_scope_key and stripped.lstrip().startswith("- "):
                scope[current_scope_key].append(parse_scalar(stripped.lstrip()[2:]))
    return {"tools": tools, "resource_scope": scope}


def allowed_from_grant(grant: dict[str, Any]) -> tuple[list[str], list[str]]:
    raw_tools = grant.get("tools", [])
    if raw_tools == "*":
        allowed = ALL_TOOLS[:]
    else:
        allowed = [tool for tool in ALL_TOOLS if tool in set(raw_tools or [])]
    forbidden = [tool for tool in ALL_TOOLS if tool not in set(allowed)]
    return allowed, forbidden


def resource_from_args(tool: str, args: dict[str, Any]) -> str:
    def first(*keys: str) -> str:
        for key in keys:
            value = args.get(key)
            if isinstance(value, str) and value:
                return value
        return "default"

    if tool.startswith("email."):
        return first("email_id", "to")
    if tool.startswith("file."):
        return first("path")
    if tool.startswith("web."):
        return first("url")
    if tool.startswith("shell."):
        return first("command")
    return "default"


def health_cmd(_: argparse.Namespace) -> None:
    try:
        result = request_json("GET", "/health")
        json_out({"ok": True, "base_url": os.environ.get("PACT_BASE_URL", DEFAULT_BASE_URL), "health": result})
    except PactError as exc:
        json_out({"ok": False, "error": str(exc)}, status=1)


def start_cmd(args: argparse.Namespace) -> None:
    grant_path = Path(args.grant or DEFAULT_GRANT_PATH).expanduser()
    if not grant_path.is_absolute():
        grant_path = (REPO_ROOT / grant_path).resolve()
    grant = parse_grant(grant_path)
    allowed, forbidden = allowed_from_grant(grant)

    agent_id = args.agent_id or f"codex-{uuid.uuid4().hex[:8]}"
    request_json(
        "GET",
        "/health",
    )
    agent = request_json(
        "POST",
        "/v1/agents/register",
        {
            "agent_id": agent_id,
            "owner": "codex",
            "agent_type": "codex_plugin",
            "allowed_domains": ALL_TOOLS,
            "risk_tier": "medium",
            "ttl_days": 30,
        },
    )
    for tool_id, meta in TOOL_METADATA.items():
        request_json("POST", "/v1/tools/register", {"tool_id": tool_id, **meta})

    intent = request_json(
        "POST",
        "/v1/intents",
        {
            "user_goal": args.goal,
            "created_by": agent_id,
            "allowed_actions": allowed,
            "forbidden_actions": forbidden,
            "resource_scope": grant.get("resource_scope", {}),
        },
    )
    run = request_json(
        "POST",
        "/v1/runs",
        {"agent_id": agent_id, "scenario_name": "codex_plugin", "user_goal": args.goal},
    )
    state = {
        "base_url": os.environ.get("PACT_BASE_URL", DEFAULT_BASE_URL),
        "agent_id": agent_id,
        "agent_private_key": agent["agent_private_key"],
        "run_id": run["run_id"],
        "intent_hash": intent["intent_hash"],
        "grant_path": str(grant_path),
        "allowed_tools": allowed,
        "forbidden_tools": forbidden,
        "resource_scope": grant.get("resource_scope", {}),
        "step_id": 0,
        "parent_action_hash": None,
        "last_decision": None,
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    save_state(state)
    json_out(
        {
            "ok": True,
            "run_id": state["run_id"],
            "agent_id": agent_id,
            "intent_hash": state["intent_hash"],
            "allowed_tools": allowed,
            "forbidden_tools": forbidden,
            "resource_scope": state["resource_scope"],
            "dashboard_hint": "Open the PACT dashboard and inspect this run_id.",
        }
    )


def check_cmd(args: argparse.Namespace) -> None:
    state = load_state()
    tool_args = json.loads(args.args_json or "{}")
    if not isinstance(tool_args, dict):
        raise PactError("--args-json must decode to a JSON object")
    tool = args.tool
    resource = resource_from_args(tool, tool_args)
    token = request_json(
        "POST",
        "/v1/capabilities",
        {
            "agent_id": state["agent_id"],
            "intent_hash": state["intent_hash"],
            "capability": tool,
            "resource": resource,
            "max_uses": 2,
            "ttl_seconds": 300,
        },
    )
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")
    envelope: dict[str, Any] = {
        "protocol": "PACT/0.1",
        "run_id": state["run_id"],
        "step_id": int(state.get("step_id", 0)),
        "agent_id": state["agent_id"],
        "tool": tool,
        "args": tool_args,
        "args_digest": hash_payload(tool_args),
        "intent_hash": state["intent_hash"],
        "capability_token_hash": token["token_hash"],
        "provenance": {},
        "parent_action_hash": state.get("parent_action_hash"),
        "timestamp": timestamp,
    }
    sign_envelope(envelope, state["agent_private_key"])
    decision = request_json(
        "POST",
        "/v1/gateway/execute",
        {"run_id": state["run_id"], "envelope": envelope, "skip_approval": args.approved},
    )
    state["step_id"] = int(state.get("step_id", 0)) + 1
    state["parent_action_hash"] = decision.get("action_hash")
    state["last_decision"] = {
        "tool": tool,
        "resource": resource,
        "decision": decision.get("decision"),
        "action_hash": decision.get("action_hash"),
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    save_state(state)
    json_out(
        {
            "ok": decision.get("decision") == "ALLOW",
            "should_proceed": decision.get("decision") == "ALLOW",
            "tool": tool,
            "resource": resource,
            **decision,
        },
        status=0 if decision.get("decision") == "ALLOW" else 2,
    )


def attach_cmd(args: argparse.Namespace) -> None:
    result = json.loads(args.result_json or "{}")
    if not isinstance(result, dict):
        raise PactError("--result-json must decode to a JSON object")
    response = request_json(
        "POST",
        f"/v1/actions/{args.action_hash}/result",
        {"result": result},
    )
    json_out({"ok": True, **response})


def status_cmd(_: argparse.Namespace) -> None:
    state = load_state()
    ledger = request_json("GET", f"/v1/runs/{state['run_id']}/ledger/verify")
    run = request_json("GET", f"/v1/runs/{state['run_id']}")
    json_out(
        {
            "ok": True,
            "run": run,
            "agent_id": state["agent_id"],
            "grant_path": state.get("grant_path"),
            "allowed_tools": state.get("allowed_tools", []),
            "forbidden_tools": state.get("forbidden_tools", []),
            "resource_scope": state.get("resource_scope", {}),
            "last_decision": state.get("last_decision"),
            "ledger": ledger,
        }
    )


def replay_cmd(_: argparse.Namespace) -> None:
    state = load_state()
    replay = request_json("GET", f"/v1/runs/{state['run_id']}/replay")
    ledger = request_json("GET", f"/v1/runs/{state['run_id']}/ledger/verify")
    steps = replay.get("steps", [])
    json_out(
        {
            "ok": True,
            "run_id": state["run_id"],
            "ledger": ledger,
            "step_count": len(steps),
            "steps": steps,
        }
    )


def complete_cmd(_: argparse.Namespace) -> None:
    state = load_state()
    result = request_json("POST", f"/v1/runs/{state['run_id']}/complete")
    json_out({"ok": True, **result})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PACT Codex plugin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health").set_defaults(func=health_cmd)

    start = sub.add_parser("start")
    start.add_argument("--goal", default="PACT-protected Codex session")
    start.add_argument("--grant")
    start.add_argument("--agent-id")
    start.set_defaults(func=start_cmd)

    check = sub.add_parser("check")
    check.add_argument("--tool", required=True, choices=ALL_TOOLS)
    check.add_argument("--args-json", default="{}")
    check.add_argument("--approved", action="store_true")
    check.set_defaults(func=check_cmd)

    attach = sub.add_parser("attach")
    attach.add_argument("--action-hash", required=True)
    attach.add_argument("--result-json", default="{}")
    attach.set_defaults(func=attach_cmd)

    sub.add_parser("status").set_defaults(func=status_cmd)
    sub.add_parser("replay").set_defaults(func=replay_cmd)
    sub.add_parser("complete").set_defaults(func=complete_cmd)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except PactError as exc:
        json_out({"ok": False, "error": str(exc)}, status=1)
    except KeyboardInterrupt:
        json_out({"ok": False, "error": "interrupted"}, status=130)


if __name__ == "__main__":
    main()
