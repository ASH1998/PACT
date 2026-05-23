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
