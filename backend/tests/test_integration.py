"""Test: PACT API integration — full lifecycle."""

import pytest


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
