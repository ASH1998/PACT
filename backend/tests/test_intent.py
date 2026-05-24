"""Test: intent classification."""

import pytest
from app.services.intent import classify_intent


class TestClassifyIntent:
    def test_summarize_email(self):
        result = classify_intent("Summarize my latest invoice email")
        assert "email.read" in result["allowed_actions"]
        assert "summarize" in result["allowed_actions"]
        assert "respond_to_user" in result["allowed_actions"]
        assert "email.send" in result["forbidden_actions"]
        assert result["risk_budget"] == "low"

    def test_send_email(self):
        result = classify_intent("Send an email to my manager")
        assert "email.read" in result["allowed_actions"]
        assert "email.send" in result["allowed_actions"]
        assert "respond_to_user" in result["allowed_actions"]

    def test_research_web(self):
        result = classify_intent("Research invoice formats on the web")
        assert "web.read" in result["allowed_actions"]
        assert "summarize" in result["allowed_actions"]
        assert "respond_to_user" in result["allowed_actions"]

    def test_unknown_goal_minimal_permissions(self):
        result = classify_intent("Do something completely unknown")
        assert result["allowed_actions"] == ["respond_to_user"]
        assert "email.read" in result["forbidden_actions"]
        assert "email.send" in result["forbidden_actions"]

    def test_read_file(self):
        result = classify_intent("Read the quarterly report file")
        assert "file.read" in result["allowed_actions"]
        assert "summarize" in result["allowed_actions"]

    def test_access_config(self):
        """G9: access+config rule allows file.read_secret and email.send, triggers R8 via secret provenance."""
        result = classify_intent("Access my config and send a summary")
        assert "file.read_secret" in result["allowed_actions"]
        assert "email.send" in result["allowed_actions"]
        assert "respond_to_user" in result["allowed_actions"]
        assert result["risk_budget"] == "medium"


# --- API-level regression tests (BUG 1, 2, 4) ---


@pytest.mark.asyncio
async def test_create_intent_upsert(client):
    """BUG 1: Creating the same intent twice should return the same intent (upsert)."""
    resp1 = await client.post("/intents/create", json={"user_goal": "Summarize my latest invoice email"})
    assert resp1.status_code == 200
    data1 = resp1.json()

    resp2 = await client.post("/intents/create", json={"user_goal": "Summarize my latest invoice email"})
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data1["intent_id"] == data2["intent_id"]
    assert data1["intent_hash"] == data2["intent_hash"]


@pytest.mark.asyncio
async def test_intent_create_returns_created_at(client):
    """BUG 2: POST /intents/create must return created_at."""
    resp = await client.post("/intents/create", json={"user_goal": "Summarize my latest invoice email"})
    assert resp.status_code == 200
    data = resp.json()
    assert "created_at" in data
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_intent_get_returns_created_at(client):
    """BUG 2: GET /intents/{id} must return created_at."""
    # Create first
    resp = await client.post("/intents/create", json={"user_goal": "Summarize my latest invoice email"})
    intent_id = resp.json()["intent_id"]

    # Get by ID
    resp2 = await client.get(f"/intents/{intent_id}")
    assert resp2.status_code == 200
    assert "created_at" in resp2.json()


@pytest.mark.asyncio
async def test_intent_classifier_word_boundary(client):
    """BUG 4: 'resend my email' should NOT match the 'send email' rule (word boundary)."""
    resp = await client.post("/intents/create", json={"user_goal": "resend my email"})
    assert resp.status_code == 200
    data = resp.json()
    # "resend" should not match "send" with word boundaries
    # It should fall through to default (only respond_to_user allowed)
    assert "email.send" not in data["allowed_actions"]
