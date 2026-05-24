"""Test: PACT API integration — full lifecycle."""

import pytest
import json


@pytest.mark.asyncio
async def test_scenario_list(client):
    """GET /scenarios returns all demo scenarios."""
    response = await client.get("/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) >= 6
    names = [s["name"] for s in scenarios]
    assert "normal_email_summary" in names
    assert "malicious_email_injection" in names


@pytest.mark.asyncio
async def test_run_normal_scenario(client):
    """POST /scenarios/run/normal_email_summary produces allowed actions."""
    response = await client.post("/scenarios/run/normal_email_summary")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["allowed_actions"] > 0
    assert data["blocked_actions"] == 0


@pytest.mark.asyncio
async def test_run_malicious_scenario_blocks(client):
    """POST /scenarios/run/malicious_email_injection blocks the attack."""
    response = await client.post("/scenarios/run/malicious_email_injection")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["blocked_actions"] > 0


@pytest.mark.asyncio
async def test_run_list(client):
    """GET /runs lists completed runs."""
    # Run a scenario first
    await client.post("/scenarios/run/normal_email_summary")
    response = await client.get("/runs")
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) >= 1


@pytest.mark.asyncio
async def test_run_detail(client):
    """GET /runs/{run_id} returns run with actions."""
    run_response = await client.post("/scenarios/run/normal_email_summary")
    run_id = run_response.json()["run_id"]
    response = await client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id
    assert len(data["actions"]) > 0


@pytest.mark.asyncio
async def test_run_replay(client):
    """GET /runs/{run_id}/replay returns replay steps."""
    run_response = await client.post("/scenarios/run/malicious_email_injection")
    run_id = run_response.json()["run_id"]
    response = await client.get(f"/runs/{run_id}/replay")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id
    assert len(data["steps"]) > 0
    # Check replay step structure
    step = data["steps"][0]
    assert "step_id" in step
    assert "tool" in step
    assert "policy_decision" in step
    assert "provenance" in step


@pytest.mark.asyncio
async def test_dashboard_overview(client):
    """GET /dashboard/overview returns metrics."""
    await client.post("/scenarios/run/normal_email_summary")
    response = await client.get("/dashboard/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["total_runs"] >= 1
    assert data["total_actions"] >= 1


@pytest.mark.asyncio
async def test_ledger_verify(client):
    """GET /runs/{run_id}/ledger/verify checks chain integrity."""
    run_response = await client.post("/scenarios/run/normal_email_summary")
    run_id = run_response.json()["run_id"]
    response = await client.get(f"/runs/{run_id}/ledger/verify")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id


@pytest.mark.asyncio
async def test_blocked_tools_call_visible_in_runs(client):
    """Blocked /tools/call should create a run visible in GET /runs."""
    # Run a scenario first to get a valid run context
    await client.post("/scenarios/run/malicious_email_injection")

    # Verify the run is in the list (not crashed)
    response = await client.get("/runs")
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) >= 1


@pytest.mark.asyncio
async def test_tools_call_missing_envelope_fields(client):
    """POST /tools/call with incomplete envelope returns 422 validation error."""
    response = await client.post("/tools/call", json={
        "envelope": {"protocol": "PACT/0.1", "run_id": "r1"},
        "run_id": "r1",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_dashboard_provenance_counts_labels_not_tools(client):
    """Verify dashboard top_provenance_sources contains provenance labels, not tool names."""
    # Run a scenario first
    resp = await client.post('/scenarios/run/malicious_email_injection')
    assert resp.status_code == 200

    # Get dashboard overview
    resp = await client.get('/dashboard/overview')
    assert resp.status_code == 200
    data = resp.json()

    sources = data['top_provenance_sources']
    # Should contain provenance labels like 'untrusted.email', 'agent.generated', 'external_write'
    # Should NOT contain tool names like 'email.read', 'email.send'
    source_names = [s['source'] for s in sources]
    assert len(source_names) > 0, "Expected at least one provenance source"
    assert any(
        'untrusted' in s or 'secret' in s or 'external' in s
        or 'agent' in s or 'trusted' in s or 'internal' in s
        for s in source_names
    ), f"Expected provenance labels, got: {source_names}"
    # Verify no tool names leaked in
    assert 'email.read' not in source_names, "Tool name should not appear in provenance sources"
    assert 'email.send' not in source_names, "Tool name should not appear in provenance sources"


@pytest.mark.asyncio
async def test_ledger_tamper_detection(client):
    """Verify ledger tamper detection catches modified actions."""
    # Run a scenario
    resp = await client.post('/scenarios/run/normal_email_summary')
    assert resp.status_code == 200
    run_id = resp.json()['run_id']

    # Verify chain is valid
    resp = await client.get(f'/runs/{run_id}/ledger/verify')
    assert resp.status_code == 200
    data = resp.json()
    assert data['valid'] is True

    # Tamper with an action directly in DB
    from app.database import async_session
    from app.models.action import Action
    from sqlalchemy import select, update

    async with async_session() as db:
        result = await db.execute(
            select(Action).where(Action.run_id == run_id).limit(1)
        )
        action = result.scalar_one_or_none()
        if action:
            await db.execute(
                update(Action).where(Action.id == action.id).values(tool='tampered_tool')
            )
            await db.commit()

    # Verify chain is now invalid
    resp = await client.get(f'/runs/{run_id}/ledger/verify')
    assert resp.status_code == 200
    data = resp.json()
    assert data['valid'] is False
    assert len(data['issues']) > 0


@pytest.mark.asyncio
async def test_secret_exfiltration_triggers_r8(client):
    """BUG 3: secret_exfiltration scenario must trigger R8 (secret + external_write), not just intent mismatch."""
    resp = await client.post("/scenarios/run/secret_exfiltration")
    assert resp.status_code == 200
    data = resp.json()

    # The scenario should have 2 steps: file.read_secret (allowed) + email.send (blocked by R8)
    assert data["total_actions"] == 2
    assert data["blocked_actions"] >= 1

    # Get run details to inspect individual actions and their policy decisions
    run_id = data["run_id"]
    run_resp = await client.get(f"/runs/{run_id}")
    assert run_resp.status_code == 200
    run_data = run_resp.json()

    # Find the email.send action — it should be blocked with R8 reason
    actions = run_data["actions"]
    email_send_action = next(a for a in actions if a["tool"] == "email.send")
    assert email_send_action["status"] == "blocked"
    pd = email_send_action["policy_decision"]
    assert pd is not None
    assert pd["decision"] == "BLOCK"
    reasons = pd["reasons"]
    assert any("Secret data may flow" in r for r in reasons), f"R8 reason missing: {reasons}"
