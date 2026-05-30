"""Tests for proxy endpoints — /v1/proxy/chat, /v1/proxy/gemini, /v1/proxy/bedrock."""

from unittest.mock import AsyncMock, patch, MagicMock

from app.adapters.providers.base import ModelResponse, ToolCall

# Register proxy and v1 routers for testing
from app.main import app as fastapi_app
from app.api.proxy import router as proxy_router
from app.api.v1 import v1_router
fastapi_app.include_router(proxy_router)
fastapi_app.include_router(v1_router, prefix="/v1")


# =========================================================================
# /v1/proxy/chat tests
# =========================================================================

class TestProxyChat:

    async def test_proxy_chat_basic(self, client):
        """Proxy chat returns provider response with event_id."""
        mock_response = ModelResponse(
            provider="openai",
            model="gpt-4o",
            raw_response={"choices": []},
            text_content="Hello from mock!",
            tool_calls=[],
            token_usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            finish_reason="stop",
        )

        with patch("app.adapters.providers.openai_compatible.OpenAICompatibleProvider") as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.invoke = AsyncMock(return_value=mock_response)
            mock_instance.name = "openai"
            # Need normalize_request to return something valid
            mock_instance.normalize_request = MagicMock(return_value=MagicMock(
                provider="openai",
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
                tool_declarations=[],
            ))

            with patch("app.api.proxy._get_provider", return_value=mock_instance):
                resp = await client.post(
                    "/v1/proxy/chat",
                    json={
                        "provider": "openai",
                        "model": "gpt-4o",
                        "messages": [{"role": "user", "content": "Hello"}],
                    },
                )

                assert resp.status_code == 200
                data = resp.json()
                assert data["text_content"] == "Hello from mock!"
                assert data["provider"] == "openai"
                assert "run_id" in data
                assert "event_id" in data
                assert data["event_id"].startswith("mevt_")

    async def test_proxy_chat_with_run_id_header(self, client):
        """X-PACT-Run-Id header creates/finds run."""
        mock_response = ModelResponse(
            provider="openai",
            model="gpt-4o",
            raw_response={},
            text_content="Response",
            tool_calls=[],
            finish_reason="stop",
        )

        mock_provider = MagicMock()
        mock_provider.invoke = AsyncMock(return_value=mock_response)
        mock_provider.name = "openai"
        mock_provider.normalize_request = MagicMock(return_value=MagicMock(
            provider="openai",
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
            tool_declarations=[],
        ))

        with patch("app.api.proxy._get_provider", return_value=mock_provider):
            resp = await client.post(
                "/v1/proxy/chat",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers={"X-PACT-Run-Id": "custom-run-123"},
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["run_id"] == "custom-run-123"

    async def test_proxy_chat_with_tool_calls(self, client):
        """Proxy chat returns tool calls from response."""
        mock_response = ModelResponse(
            provider="openai",
            model="gpt-4o",
            raw_response={},
            text_content="Let me search.",
            tool_calls=[
                ToolCall(tool_id="search", args={"query": "PACT"}, tool_call_id="call_1"),
            ],
            token_usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            finish_reason="tool_calls",
        )

        mock_provider = MagicMock()
        mock_provider.invoke = AsyncMock(return_value=mock_response)
        mock_provider.name = "openai"
        mock_provider.normalize_request = MagicMock(return_value=MagicMock(
            provider="openai",
            model="gpt-4o",
            messages=[{"role": "user", "content": "Search for PACT"}],
            tool_declarations=[],
        ))

        with patch("app.api.proxy._get_provider", return_value=mock_provider):
            resp = await client.post(
                "/v1/proxy/chat",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "Search for PACT"}],
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert len(data["tool_calls"]) == 1
            assert data["tool_calls"][0]["tool_id"] == "search"
            assert data["tool_calls"][0]["args"] == {"query": "PACT"}
            assert data["finish_reason"] == "tool_calls"

    async def test_proxy_chat_creates_run_in_db(self, client):
        """Proxy chat creates a run record in the database."""
        mock_response = ModelResponse(
            provider="openai",
            model="gpt-4o",
            raw_response={},
            text_content="OK",
            tool_calls=[],
            finish_reason="stop",
        )

        mock_provider = MagicMock()
        mock_provider.invoke = AsyncMock(return_value=mock_response)
        mock_provider.name = "openai"
        mock_provider.normalize_request = MagicMock(return_value=MagicMock(
            provider="openai",
            model="gpt-4o",
            messages=[{"role": "user", "content": "Test"}],
            tool_declarations=[],
        ))

        with patch("app.api.proxy._get_provider", return_value=mock_provider):
            resp = await client.post(
                "/v1/proxy/chat",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "Test"}],
                    "agent_id": "test-agent",
                },
            )

            assert resp.status_code == 200
            run_id = resp.json()["run_id"]

            # Verify run exists
            run_resp = await client.get(f"/runs/{run_id}")
            assert run_resp.status_code == 200
            assert run_resp.json()["run_id"] == run_id

    async def test_proxy_chat_persists_model_event_to_db(self, client, setup_db):
        """Model events are persisted to the model_events table."""
        from app.database import async_session
        from app.models.model_event import ModelEvent
        from sqlalchemy import select

        mock_response = ModelResponse(
            provider="openai",
            model="gpt-4o",
            raw_response={"choices": []},
            text_content="Persisted!",
            tool_calls=[],
            token_usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            finish_reason="stop",
        )

        mock_provider = MagicMock()
        mock_provider.invoke = AsyncMock(return_value=mock_response)
        mock_provider.name = "openai"
        mock_provider.normalize_request = MagicMock(return_value=MagicMock(
            provider="openai",
            model="gpt-4o",
            messages=[{"role": "user", "content": "Test"}],
            tool_declarations=[],
        ))

        with patch("app.api.proxy._get_provider", return_value=mock_provider):
            resp = await client.post(
                "/v1/proxy/chat",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "Test"}],
                },
            )

            assert resp.status_code == 200
            event_id = resp.json()["event_id"]

            # Verify event exists in DB
            async with async_session() as db:
                result = await db.execute(select(ModelEvent).where(ModelEvent.event_id == event_id))
                event = result.scalar_one_or_none()
                assert event is not None
                assert event.provider == "openai"
                assert event.model == "gpt-4o"
                assert event.run_id == resp.json()["run_id"]

    async def test_proxy_chat_creates_provenance_event(self, client, setup_db):
        """Proxy chat creates a provenance_events record."""
        from app.database import async_session
        from app.models.provenance_event import ProvenanceEvent
        from sqlalchemy import select

        mock_response = ModelResponse(
            provider="openai",
            model="gpt-4o",
            raw_response={},
            text_content="Provenance test",
            tool_calls=[],
            finish_reason="stop",
        )

        mock_provider = MagicMock()
        mock_provider.invoke = AsyncMock(return_value=mock_response)
        mock_provider.name = "openai"
        mock_provider.normalize_request = MagicMock(return_value=MagicMock(
            provider="openai",
            model="gpt-4o",
            messages=[{"role": "user", "content": "Test"}],
            tool_declarations=[],
        ))

        with patch("app.api.proxy._get_provider", return_value=mock_provider):
            resp = await client.post(
                "/v1/proxy/chat",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "Test"}],
                },
            )

            assert resp.status_code == 200
            run_id = resp.json()["run_id"]

            # Verify provenance event exists in DB
            async with async_session() as db:
                result = await db.execute(select(ProvenanceEvent).where(ProvenanceEvent.run_id == run_id))
                events = result.scalars().all()
                assert len(events) >= 1
                prov = events[0]
                assert prov.source_type == "model_output"
                assert prov.source_label == "agent.generated"
                assert prov.content_digest is not None
                assert "openai" in prov.metadata_json

    async def test_proxy_chat_gemini_provider(self, client):
        """Proxy chat with Gemini provider."""
        mock_response = ModelResponse(
            provider="gemini",
            model="gemini-pro",
            raw_response={},
            text_content="Gemini says hello!",
            tool_calls=[],
            finish_reason="STOP",
        )

        mock_provider = MagicMock()
        mock_provider.invoke = AsyncMock(return_value=mock_response)
        mock_provider.name = "gemini"
        mock_provider.normalize_request = MagicMock(return_value=MagicMock(
            provider="gemini",
            model="gemini-pro",
            messages=[{"role": "user", "content": "Hello"}],
            tool_declarations=[],
        ))

        with patch("app.api.proxy._get_provider", return_value=mock_provider):
            resp = await client.post(
                "/v1/proxy/chat",
                json={
                    "provider": "gemini",
                    "model": "gemini-pro",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["provider"] == "gemini"
            assert data["text_content"] == "Gemini says hello!"

    async def test_proxy_chat_bedrock_provider(self, client):
        """Proxy chat with Bedrock provider."""
        mock_response = ModelResponse(
            provider="bedrock",
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            raw_response={},
            text_content="Bedrock says hello!",
            tool_calls=[],
            finish_reason="end_turn",
        )

        mock_provider = MagicMock()
        mock_provider.invoke = AsyncMock(return_value=mock_response)
        mock_provider.name = "bedrock"
        mock_provider.normalize_request = MagicMock(return_value=MagicMock(
            provider="bedrock",
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            messages=[{"role": "user", "content": "Hello"}],
            tool_declarations=[],
        ))

        with patch("app.api.proxy._get_provider", return_value=mock_provider):
            resp = await client.post(
                "/v1/proxy/chat",
                json={
                    "provider": "bedrock",
                    "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["provider"] == "bedrock"
            assert data["text_content"] == "Bedrock says hello!"

    async def test_proxy_chat_unknown_provider(self, client):
        """Returns 400 for unknown provider."""
        resp = await client.post(
            "/v1/proxy/chat",
            json={
                "provider": "nonexistent",
                "model": "test",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert resp.status_code == 400


# =========================================================================
# /v1/proxy/bedrock/converse tests
# =========================================================================

class TestProxyBedrock:

    async def test_proxy_bedrock_basic(self, client):
        """Bedrock proxy forwards request and returns response."""
        mock_response = ModelResponse(
            provider="bedrock",
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            raw_response={
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [{"text": "Hello from Bedrock!"}],
                    }
                },
                "stopReason": "end_turn",
                "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
            },
            text_content="Hello from Bedrock!",
            finish_reason="end_turn",
        )

        mock_provider = MagicMock()
        mock_provider.invoke = AsyncMock(return_value=mock_response)
        mock_provider.name = "bedrock"
        mock_provider.normalize_request = MagicMock(return_value=MagicMock(
            provider="bedrock",
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            tool_declarations=[],
        ))

        with patch("app.api.proxy._get_provider", return_value=mock_provider):
            resp = await client.post(
                "/v1/proxy/bedrock/converse",
                json={
                    "messages": [{"role": "user", "content": [{"text": "Hello"}]}],
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert "output" in data
            assert data["stopReason"] == "end_turn"
