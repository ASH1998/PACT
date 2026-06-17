"""Tests for v1 API surface — runs, actions, tools, policies, approvals, intents, capabilities."""


# Register proxy and v1 routers for testing
from app.main import app as fastapi_app
from app.api.proxy import router as proxy_router
from app.api.v1 import v1_router
fastapi_app.include_router(proxy_router)
fastapi_app.include_router(v1_router, prefix="/v1")


# =========================================================================
# V1 Runs Tests
# =========================================================================

class TestV1Runs:

    async def test_create_run(self, client):
        """POST /v1/runs creates a new run."""
        resp = await client.post(
            "/v1/runs",
            json={"agent_id": "test-agent", "user_goal": "test goal"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["agent_id"] == "test-agent"
        assert data["user_goal"] == "test goal"
        assert data["status"] == "running"

    async def test_get_run(self, client):
        """GET /v1/runs/{run_id} returns run details."""
        # Create a run first
        create_resp = await client.post(
            "/v1/runs",
            json={"agent_id": "test-agent"},
        )
        run_id = create_resp.json()["run_id"]

        # Get the run
        resp = await client.get(f"/v1/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["agent_id"] == "test-agent"

    async def test_get_run_not_found(self, client):
        """GET /v1/runs/{run_id} returns 404 for unknown run."""
        resp = await client.get("/v1/runs/nonexistent")
        assert resp.status_code == 404

    async def test_get_run_replay(self, client):
        """GET /v1/runs/{run_id}/replay returns replay data."""
        create_resp = await client.post(
            "/v1/runs",
            json={"agent_id": "test-agent"},
        )
        run_id = create_resp.json()["run_id"]

        resp = await client.get(f"/v1/runs/{run_id}/replay")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert "steps" in data

    async def test_verify_ledger(self, client):
        """GET /v1/runs/{run_id}/ledger/verify returns verification result."""
        create_resp = await client.post(
            "/v1/runs",
            json={"agent_id": "test-agent"},
        )
        run_id = create_resp.json()["run_id"]

        resp = await client.get(f"/v1/runs/{run_id}/ledger/verify")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert "valid" in data


# =========================================================================
# V1 Actions Tests
# =========================================================================

class TestV1Actions:

    async def test_propose_action(self, client):
        """POST /v1/actions/propose evaluates an action."""
        # Create a run
        run_resp = await client.post(
            "/v1/runs",
            json={"agent_id": "test-agent"},
        )
        run_id = run_resp.json()["run_id"]

        # Propose an action (no passport exists, so should be blocked)
        resp = await client.post(
            "/v1/actions/propose",
            json={
                "run_id": run_id,
                "agent_id": "test-agent",
                "tool": "email.send",
                "args": {"to": "test@example.com", "body": "Hello"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "decision" in data
        assert "risk_score" in data
        assert "action_hash" in data

    async def test_propose_action_run_not_found(self, client):
        """POST /v1/actions/propose returns 404 for unknown run."""
        resp = await client.post(
            "/v1/actions/propose",
            json={
                "run_id": "nonexistent",
                "agent_id": "test-agent",
                "tool": "email.send",
            },
        )
        assert resp.status_code == 404

    async def test_execute_action_not_found(self, client):
        """POST /v1/actions/{id}/execute returns 404 for unknown action."""
        resp = await client.post("/v1/actions/nonexistent/execute")
        assert resp.status_code == 404


# =========================================================================
# V1 Tools Tests
# =========================================================================

class TestV1Tools:

    async def test_register_tool(self, client):
        """POST /v1/tools/register registers a tool."""
        resp = await client.post(
            "/v1/tools/register",
            json={
                "tool_id": "test_search",
                "name": "Search",
                "description": "Search the web",
                "parameters": {"query": {"type": "string"}},
                "side_effect": "read", "sensitivity": "low",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_id"] == "test_search"
        assert data["name"] == "Search"
        assert data["side_effect"] == "read"
        assert data["sensitivity"] == "low"

    async def test_list_tools(self, client):
        """GET /v1/tools lists registered tools."""
        # Register a tool first
        await client.post(
            "/v1/tools/register",
            json={
                "tool_id": "tool_a",
                "name": "Tool A",
                "description": "First tool",
            },
        )

        resp = await client.get("/v1/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert data["count"] >= 1

    async def test_get_tool(self, client):
        """GET /v1/tools/{tool_id} returns tool details."""
        await client.post(
            "/v1/tools/register",
            json={
                "tool_id": "specific_tool",
                "name": "Specific",
                "description": "A specific tool",
            },
        )

        resp = await client.get("/v1/tools/specific_tool")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_id"] == "specific_tool"
        assert data["name"] == "Specific"

    async def test_get_tool_not_found(self, client):
        """GET /v1/tools/{tool_id} returns 404 for unknown tool."""
        resp = await client.get("/v1/tools/nonexistent")
        assert resp.status_code == 404


# =========================================================================
# V1 Policies Tests
# =========================================================================

class TestV1Policies:

    async def test_create_policy(self, client):
        """POST /v1/policies creates a policy."""
        resp = await client.post(
            "/v1/policies",
            json={
                "policy_id": "test_policy",
                "name": "Test Policy",
                "description": "A test policy",
                "rules": [{"tool": "email.send", "max_per_hour": 10}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["policy_id"] == "test_policy"
        assert data["name"] == "Test Policy"
        assert len(data["rules"]) == 1

    async def test_list_policies(self, client):
        """GET /v1/policies lists active policies."""
        await client.post(
            "/v1/policies",
            json={
                "policy_id": "active_policy",
                "name": "Active",
                "enabled": True,
            },
        )

        resp = await client.get("/v1/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert "policies" in data
        assert data["count"] >= 1

    async def test_get_policy(self, client):
        """GET /v1/policies/{policy_id} returns persisted policy details."""
        await client.post(
            "/v1/policies",
            json={
                "policy_id": "specific_policy",
                "name": "Specific",
                "rules": [{"condition": {"tool_prefix": "email."}, "action": "BLOCK"}],
            },
        )

        resp = await client.get("/v1/policies/specific_policy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["policy_id"] == "specific_policy"
        assert data["name"] == "Specific"
        assert data["enabled"] is True

    async def test_disabled_policy_is_not_listed(self, client):
        """GET /v1/policies excludes disabled policies."""
        await client.post(
            "/v1/policies",
            json={
                "policy_id": "disabled_policy",
                "name": "Disabled",
                "enabled": False,
            },
        )

        resp = await client.get("/v1/policies")
        assert resp.status_code == 200
        policy_ids = {p["policy_id"] for p in resp.json()["policies"]}
        assert "disabled_policy" not in policy_ids

    async def test_structured_policy_reloads_runtime(self, client):
        """Structured rules posted through the API are applied to PactRuntime."""
        from app.core.factory import get_runtime, reset_runtime

        await client.post(
            "/v1/policies",
            json={
                "policy_id": "runtime_block_read",
                "name": "Block read tools",
                "rules": [
                    {
                        "id": "block-read",
                        "condition": {"side_effect": "read"},
                        "action": "BLOCK",
                        "severity": "high",
                        "risk_score": 70,
                        "reason": "Read tools are blocked by persisted policy",
                    }
                ],
            },
        )

        try:
            rules = get_runtime().policy_service.config.rules
            assert any(rule.get("id") == "block-read" for rule in rules)
            assert any(rule.get("id") == "R1-invalid-passport" for rule in rules)
        finally:
            reset_runtime()


# =========================================================================
# V1 Approvals Tests
# =========================================================================

class TestV1Approvals:

    async def test_approve_action_not_found(self, client):
        """POST /v1/approvals/{id}/approve returns 404 for nonexistent approval."""
        resp = await client.post("/v1/approvals/nonexistent/approve")
        assert resp.status_code == 404

    async def test_deny_action_not_found(self, client):
        """POST /v1/approvals/{id}/deny returns 404 for nonexistent approval."""
        resp = await client.post("/v1/approvals/nonexistent/deny")
        assert resp.status_code == 404

    async def test_approve_wrong_status(self, client):
        """POST /v1/approvals/{id}/approve returns 400 for already-decided approval."""
        from app.services.approval import ApprovalService
        from app.database import async_session

        svc = ApprovalService()
        async with async_session() as db:
            # Create an approval record
            created = await svc.create_approval(
                db=db,
                run_id="run_test_status",
                action_hash="ah_test_status",
                agent_id="test-agent",
                envelope_json='{"test": true}',
            )
            # Approve it once
            await svc.approve(
                db=db, approval_id=created["approval_id"], decided_by="admin"
            )

        # Now try to approve again — should fail because it's already approved
        resp = await client.post(
            f"/v1/approvals/{created['approval_id']}/approve"
        )
        assert resp.status_code == 400

    async def test_approve_real_approval(self, client):
        """POST /v1/approvals/{id}/approve works for a real pending approval."""
        from app.services.approval import ApprovalService
        from app.database import async_session

        svc = ApprovalService()
        async with async_session() as db:
            created = await svc.create_approval(
                db=db,
                run_id="run_test_approve",
                action_hash="ah_test_approve",
                agent_id="test-agent",
                envelope_json='{"test": "approve"}',
            )

        approval_id = created["approval_id"]
        resp = await client.post(
            f"/v1/approvals/{approval_id}/approve?decided_by=test_user&reason=looks+good"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_id"] == approval_id
        assert data["status"] == "approved"
        assert data["decided_by"] == "test_user"

    async def test_deny_real_approval(self, client):
        """POST /v1/approvals/{id}/deny works for a real pending approval."""
        from app.services.approval import ApprovalService
        from app.database import async_session

        svc = ApprovalService()
        async with async_session() as db:
            created = await svc.create_approval(
                db=db,
                run_id="run_test_deny",
                action_hash="ah_test_deny",
                agent_id="test-agent",
                envelope_json='{"test": "deny"}',
            )

        approval_id = created["approval_id"]
        resp = await client.post(
            f"/v1/approvals/{approval_id}/deny?decided_by=reviewer&reason=too+risky"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_id"] == approval_id
        assert data["status"] == "denied"
        assert data["decided_by"] == "reviewer"

    async def test_list_approvals(self, client):
        """GET /v1/approvals lists approvals."""
        from app.services.approval import ApprovalService
        from app.database import async_session

        svc = ApprovalService()
        async with async_session() as db:
            await svc.create_approval(
                db=db,
                run_id="run_list_1",
                action_hash="ah_list_1",
                agent_id="agent-1",
                envelope_json="{}",
            )
            await svc.create_approval(
                db=db,
                run_id="run_list_2",
                action_hash="ah_list_2",
                agent_id="agent-2",
                envelope_json="{}",
            )

        resp = await client.get("/v1/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert "approvals" in data
        assert data["count"] >= 2

    async def test_get_approval(self, client):
        """GET /v1/approvals/{id} returns approval details."""
        from app.services.approval import ApprovalService
        from app.database import async_session

        svc = ApprovalService()
        async with async_session() as db:
            created = await svc.create_approval(
                db=db,
                run_id="run_get_appr",
                action_hash="ah_get_appr",
                agent_id="test-agent",
                envelope_json='{"key": "value"}',
            )

        approval_id = created["approval_id"]
        resp = await client.get(f"/v1/approvals/{approval_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_id"] == approval_id
        assert data["status"] == "pending"

    async def test_get_approval_not_found(self, client):
        """GET /v1/approvals/{id} returns 404 for nonexistent approval."""
        resp = await client.get("/v1/approvals/nonexistent")
        assert resp.status_code == 404


# =========================================================================
# V1 Intents Tests
# =========================================================================

class TestV1Intents:

    async def test_create_intent_programmatic(self, client):
        """POST /v1/intents with programmatic allowed/forbidden actions."""
        resp = await client.post(
            "/v1/intents",
            json={
                "user_goal": "Send marketing emails",
                "created_by": "test-user",
                "allowed_actions": ["email.send", "email.read"],
                "forbidden_actions": ["email.delete"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "intent_id" in data
        assert data["user_goal"] == "Send marketing emails"
        assert "email.send" in data["allowed_actions"]
        assert "email.delete" in data["forbidden_actions"]
        assert "intent_hash" in data

    async def test_create_intent_keyword(self, client):
        """POST /v1/intents with just user_goal (keyword mode)."""
        resp = await client.post(
            "/v1/intents",
            json={"user_goal": "Read my emails"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "intent_id" in data
        assert "intent_hash" in data

    async def test_list_intents(self, client):
        """GET /v1/intents lists intents."""
        # Create an intent first
        await client.post(
            "/v1/intents",
            json={
                "user_goal": "Test listing",
                "allowed_actions": ["tool.a"],
            },
        )

        resp = await client.get("/v1/intents")
        assert resp.status_code == 200
        data = resp.json()
        assert "intents" in data
        assert data["count"] >= 1
        # Verify structure of returned intents
        intent = data["intents"][0]
        assert "intent_id" in intent
        assert "user_goal" in intent
        assert "allowed_actions" in intent
        assert "forbidden_actions" in intent
        assert "intent_hash" in intent

    async def test_get_intent(self, client):
        """GET /v1/intents/{id} returns intent details."""
        create_resp = await client.post(
            "/v1/intents",
            json={
                "user_goal": "Get specific intent",
                "allowed_actions": ["tool.x"],
                "forbidden_actions": ["tool.y"],
            },
        )
        intent_id = create_resp.json()["intent_id"]

        resp = await client.get(f"/v1/intents/{intent_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == intent_id
        assert "tool.x" in data["allowed_actions"]

    async def test_get_intent_not_found(self, client):
        """GET /v1/intents/{id} returns 404 for unknown intent."""
        resp = await client.get("/v1/intents/nonexistent_intent")
        assert resp.status_code == 404

    async def test_create_intent_programmatic_dedup(self, client):
        """POST /v1/intents with same programmatic actions returns same intent."""
        payload = {
            "user_goal": "Dedup test",
            "created_by": "test-user",
            "allowed_actions": ["tool.a", "tool.b"],
            "forbidden_actions": ["tool.c"],
        }
        resp1 = await client.post("/v1/intents", json=payload)
        resp2 = await client.post("/v1/intents", json=payload)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["intent_id"] == resp2.json()["intent_id"]


# =========================================================================
# V1 Agents Tests
# =========================================================================

class TestV1Agents:

    async def test_register_agent_requires_demo_opt_in(self, client):
        """POST /v1/agents/register rejects private-key issuance unless enabled."""
        from app.config import settings

        previous = settings.allow_insecure_demo_api
        settings.allow_insecure_demo_api = False
        try:
            resp = await client.post(
                "/v1/agents/register",
                json={
                    "agent_id": "guarded-agent",
                    "owner": "test",
                    "allowed_domains": ["respond_to_user"],
                },
            )
        finally:
            settings.allow_insecure_demo_api = previous

        assert resp.status_code == 403
        assert "demo-only" in resp.json()["detail"]


# =========================================================================
# V1 Capabilities Tests
# =========================================================================

class TestV1Capabilities:

    async def test_issue_capability_requires_demo_opt_in(self, client):
        """POST /v1/capabilities rejects demo authority issuance unless enabled."""
        from app.config import settings

        previous = settings.allow_insecure_demo_api
        settings.allow_insecure_demo_api = False
        try:
            resp = await client.post(
                "/v1/capabilities",
                json={
                    "agent_id": "test-agent",
                    "intent_hash": "sha256:test",
                    "capability": "email.send",
                    "resource": "test@example.com",
                },
            )
        finally:
            settings.allow_insecure_demo_api = previous

        assert resp.status_code == 403
        assert "demo-only" in resp.json()["detail"]

    async def test_issue_capability(self, client):
        """POST /v1/capabilities issues a capability token."""
        # First create an intent to get a valid intent_hash
        intent_resp = await client.post(
            "/v1/intents",
            json={
                "user_goal": "Capability test",
                "allowed_actions": ["email.send"],
            },
        )
        intent_hash = intent_resp.json()["intent_hash"]

        resp = await client.post(
            "/v1/capabilities",
            json={
                "agent_id": "test-agent",
                "intent_hash": intent_hash,
                "capability": "email.send",
                "resource": "test@example.com",
                "max_uses": 5,
                "ttl_seconds": 300,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token_hash" in data
        assert data["agent_id"] == "test-agent"
        assert data["capability"] == "email.send"
        assert data["resource"] == "test@example.com"
        assert data["max_uses"] == 5
