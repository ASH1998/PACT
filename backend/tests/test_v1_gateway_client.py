"""External-agent client flow: register -> intent (with resource_scope) -> run
-> issue capability -> client-signed envelope -> /v1/gateway/execute (no
server-side tool execution) -> attach client result -> verify ledger.

Envelopes are signed with the real EnvelopeService, which is byte-for-byte
identical to what the Go TUI client produces (proven by the crypto parity check).
"""

from app.services.envelope import EnvelopeService
from app.tools.resource import resource_from_args

AGENT_ID = "go-cli-1"


async def _bootstrap(client, *, allowed, resource_scope, goal="client flow"):
    reg = await client.post(
        "/v1/agents/register",
        json={
            "agent_id": AGENT_ID,
            "owner": "local",
            "agent_type": "go_tui",
            "allowed_domains": allowed,
        },
    )
    assert reg.status_code == 200, reg.text
    priv = reg.json()["agent_private_key"]

    for tid, rtype, se, sens, approve in [
        ("email.send", "email_address", "external_write", "high", False),
        ("web.read", "url", "read", "medium", False),
        ("file.read_secret", "file_path", "read", "critical", True),
    ]:
        r = await client.post(
            "/v1/tools/register",
            json={
                "tool_id": tid,
                "name": tid,
                "side_effect": se,
                "sensitivity": sens,
                "resource_type": rtype,
                "requires_approval": approve,
            },
        )
        assert r.status_code == 200, r.text

    intent = await client.post(
        "/v1/intents",
        json={
            "user_goal": goal,
            "created_by": AGENT_ID,
            "allowed_actions": allowed,
            "forbidden_actions": [],
            "resource_scope": resource_scope,
        },
    )
    assert intent.status_code == 200, intent.text
    # resource_scope must be reflected back and fold into the tamper-evident hash
    assert intent.json().get("resource_scope") == resource_scope
    intent_hash = intent.json()["intent_hash"]

    run = await client.post("/v1/runs", json={"agent_id": AGENT_ID, "user_goal": goal})
    return priv, intent_hash, run.json()["run_id"]


async def _submit(client, *, priv, intent_hash, run_id, tool, args, skip_approval=False):
    resource = resource_from_args(tool, args)
    cap = await client.post(
        "/v1/capabilities",
        json={
            "agent_id": AGENT_ID,
            "intent_hash": intent_hash,
            "capability": tool,
            "resource": resource,
            "max_uses": 2,
            "ttl_seconds": 300,
        },
    )
    assert cap.status_code == 200, cap.text
    env = EnvelopeService().create_envelope(
        agent_id=AGENT_ID,
        agent_private_key=priv,
        run_id=run_id,
        step_id=0,
        tool=tool,
        args=args,
        intent_hash=intent_hash,
        capability_token_hash=cap.json()["token_hash"],
        provenance={},
        parent_action_hash=None,
    )
    resp = await client.post(
        "/v1/gateway/execute",
        json={"run_id": run_id, "envelope": env, "skip_approval": skip_approval},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestExternalClientGateway:
    async def test_out_of_scope_email_blocked_structurally(self, client):
        """An out-of-scope recipient is BLOCKED by R12 — no keyword matching."""
        priv, intent_hash, run_id = await _bootstrap(
            client,
            allowed=["email.send"],
            resource_scope={"email_address": ["*@acme.com"]},
        )
        out = await _submit(
            client,
            priv=priv,
            intent_hash=intent_hash,
            run_id=run_id,
            tool="email.send",
            args={"to": "attacker@evil.com", "subject": "x", "body": "y"},
        )
        assert out["decision"] == "BLOCK"
        assert any("scope" in r.lower() for r in out["reasons"])

    async def test_in_scope_email_not_blocked_by_scope(self, client):
        """An in-scope recipient passes the R12 scope check."""
        priv, intent_hash, run_id = await _bootstrap(
            client,
            allowed=["email.send"],
            resource_scope={"email_address": ["*@acme.com"]},
        )
        out = await _submit(
            client,
            priv=priv,
            intent_hash=intent_hash,
            run_id=run_id,
            tool="email.send",
            args={"to": "bob@acme.com", "subject": "x", "body": "y"},
        )
        assert out["decision"] != "BLOCK"
        assert not any("scope" in r.lower() for r in out["reasons"])

    async def test_allow_records_ledger_and_attaches_client_result(self, client):
        """ALLOW path: gateway records the action but does NOT execute the tool;
        the client attaches its locally-produced result and the ledger verifies."""
        priv, intent_hash, run_id = await _bootstrap(
            client,
            allowed=["web.read"],
            resource_scope={"url": ["*"]},
        )
        out = await _submit(
            client,
            priv=priv,
            intent_hash=intent_hash,
            run_id=run_id,
            tool="web.read",
            args={"url": "https://example.com"},
        )
        assert out["decision"] == "ALLOW"
        action_hash = out["action_hash"]

        attach = await client.post(
            f"/v1/actions/{action_hash}/result",
            json={"result": {"status": "ok", "title": "Example", "client_executed": True}},
        )
        assert attach.status_code == 200, attach.text
        assert attach.json()["recorded"] is True

        ver = await client.get(f"/v1/runs/{run_id}/ledger/verify")
        assert ver.status_code == 200
        assert ver.json()["valid"] is True

    async def test_attach_result_unknown_action_404(self, client):
        resp = await client.post(
            "/v1/actions/sha256:deadbeef/result", json={"result": {"x": 1}}
        )
        assert resp.status_code == 404

    async def test_secret_read_requires_approval_then_skip_allows(self, client):
        """file.read_secret -> REQUIRE_APPROVAL (R11); skip_approval -> ALLOW."""
        priv, intent_hash, run_id = await _bootstrap(
            client,
            allowed=["file.read_secret"],
            resource_scope={"file_path": ["*"]},
        )
        pending = await _submit(
            client,
            priv=priv,
            intent_hash=intent_hash,
            run_id=run_id,
            tool="file.read_secret",
            args={"path": ".env"},
        )
        assert pending["decision"] == "REQUIRE_APPROVAL"

        approved = await _submit(
            client,
            priv=priv,
            intent_hash=intent_hash,
            run_id=run_id,
            tool="file.read_secret",
            args={"path": ".env"},
            skip_approval=True,
        )
        assert approved["decision"] == "ALLOW"


class TestV1RunExtras:
    async def test_record_model_event_and_complete(self, client):
        run = await client.post("/v1/runs", json={"agent_id": AGENT_ID})
        run_id = run.json()["run_id"]

        ev = await client.post(
            f"/v1/runs/{run_id}/model-events",
            json={
                "provider": "claude",
                "model": "claude-x",
                "request_json": "{}",
                "response_json": "{}",
                "tool_calls": [{"name": "web_read", "args": {"url": "https://x"}}],
                "token_usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )
        assert ev.status_code == 200, ev.text
        assert ev.json()["run_id"] == run_id

        done = await client.post(f"/v1/runs/{run_id}/complete")
        assert done.status_code == 200
        assert done.json()["status"] == "completed"

    async def test_model_event_unknown_run_404(self, client):
        resp = await client.post(
            "/v1/runs/nope/model-events",
            json={"provider": "x", "model": "y"},
        )
        assert resp.status_code == 404
