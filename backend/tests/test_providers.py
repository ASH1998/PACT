"""Tests for provider adapters — Gemini, Bedrock, OpenAI-compatible."""

from unittest.mock import AsyncMock, patch, MagicMock

from app.adapters.providers.base import ModelRequest
from app.adapters.providers.gemini import GeminiProvider
from app.adapters.providers.bedrock import BedrockProvider
from app.adapters.providers.openai_compatible import OpenAICompatibleProvider


# =========================================================================
# Gemini Provider Tests
# =========================================================================

class TestGeminiProvider:

    def setup_method(self):
        self.provider = GeminiProvider(api_key="test-key")

    def test_normalize_request_basic(self):
        """Gemini generateContent format -> ModelRequest."""
        raw = {
            "contents": [
                {"role": "user", "parts": [{"text": "Hello"}]},
            ],
            "model": "gemini-pro",
        }
        req = self.provider.normalize_request(raw)
        assert req.provider == "gemini"
        assert req.model == "gemini-pro"
        assert len(req.messages) == 1
        assert req.messages[0]["role"] == "user"
        assert req.messages[0]["content"] == "Hello"

    def test_normalize_request_openai_style_messages(self):
        """Provider-agnostic proxy chat messages -> ModelRequest."""
        raw = {
            "model": "gemini-flash",
            "messages": [
                {"role": "system", "content": "Be terse"},
                {"role": "user", "content": "Hello"},
            ],
        }
        req = self.provider.normalize_request(raw)
        assert req.provider == "gemini"
        assert req.model == "gemini-flash"
        assert req.messages == [
            {"role": "system", "content": "Be terse"},
            {"role": "user", "content": "Hello"},
        ]

    def test_uses_google_env_aliases(self, monkeypatch):
        """Gemini provider accepts Google-style env names from .env files."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
        monkeypatch.setenv("GOOGLE_MODEL", "gemini-env-model")

        provider = GeminiProvider()
        req = provider.normalize_request({"contents": []})

        assert provider.api_key == "google-key"
        assert req.model == "gemini-env-model"

    def test_normalize_request_with_system(self):
        """System instruction becomes a system message."""
        raw = {
            "contents": [
                {"role": "user", "parts": [{"text": "Hi"}]},
            ],
            "systemInstruction": {"parts": [{"text": "You are helpful"}]},
        }
        # normalize_request doesn't handle systemInstruction — it's in the invoke path
        req = self.provider.normalize_request(raw)
        assert len(req.messages) == 1

    def test_normalize_request_with_tools(self):
        """Extracts function declarations from tools."""
        raw = {
            "contents": [{"role": "user", "parts": [{"text": "Search"}]}],
            "tools": [
                {
                    "functionDeclarations": [
                        {"name": "search", "description": "Search the web"},
                    ]
                }
            ],
        }
        req = self.provider.normalize_request(raw)
        assert len(req.tool_declarations) == 1
        assert req.tool_declarations[0]["name"] == "search"

    def test_normalize_response_text_only(self):
        """Extracts text from Gemini response."""
        raw = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Hello there!"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
            "model": "gemini-pro",
        }
        resp = self.provider.normalize_response(raw)
        assert resp.provider == "gemini"
        assert resp.text_content == "Hello there!"
        assert resp.finish_reason == "STOP"
        assert resp.token_usage["prompt_tokens"] == 10
        assert resp.token_usage["completion_tokens"] == 5
        assert resp.token_usage["total_tokens"] == 15
        assert len(resp.tool_calls) == 0

    def test_normalize_response_with_function_call(self):
        """Extracts function calls from Gemini response."""
        raw = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Let me search for that."},
                            {
                                "functionCall": {
                                    "name": "web_search",
                                    "args": {"query": "PACT security"},
                                }
                            },
                        ]
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 15, "totalTokenCount": 35},
        }
        resp = self.provider.normalize_response(raw)
        assert resp.text_content == "Let me search for that."
        assert len(resp.tool_calls) == 1
        tc = resp.tool_calls[0]
        assert tc.tool_id == "web_search"
        assert tc.args == {"query": "PACT security"}

    def test_normalize_response_multiple_function_calls(self):
        """Handles multiple function calls in one response."""
        raw = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"functionCall": {"name": "tool_a", "args": {"x": 1}}},
                            {"functionCall": {"name": "tool_b", "args": {"y": 2}}},
                        ]
                    },
                    "finishReason": "STOP",
                }
            ],
        }
        resp = self.provider.normalize_response(raw)
        assert len(resp.tool_calls) == 2
        assert resp.tool_calls[0].tool_id == "tool_a"
        assert resp.tool_calls[1].tool_id == "tool_b"

    def test_normalize_response_with_safety_ratings(self):
        """Preserves safety ratings."""
        raw = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Safe response"}]},
                    "finishReason": "STOP",
                    "safetyRatings": [
                        {"category": "HARM_CATEGORY_HARASSMENT", "probability": "NEGLIGIBLE"}
                    ],
                }
            ],
        }
        resp = self.provider.normalize_response(raw)
        assert resp.safety_ratings is not None
        assert len(resp.safety_ratings) == 1

    def test_normalize_response_empty_candidates(self):
        """Handles empty candidates gracefully."""
        raw = {"candidates": []}
        resp = self.provider.normalize_response(raw)
        assert resp.text_content == ""
        assert resp.tool_calls == []

    async def test_invoke_makes_http_call(self):
        """invoke() calls the Gemini API with correct format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "API response"}]}, "finishReason": "STOP"}
            ],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            req = ModelRequest(
                provider="gemini",
                model="gemini-pro",
                messages=[{"role": "user", "content": "Hello"}],
            )
            resp = await self.provider.invoke(req)

            assert resp.text_content == "API response"
            assert resp.provider == "gemini"

            # Verify the HTTP call was made
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            url = call_args[0][0]
            assert "gemini-pro" in url
            assert "generateContent" in url
            assert "key=" not in url
            assert call_args.kwargs["headers"]["x-goog-api-key"] == "test-key"


# =========================================================================
# Bedrock Provider Tests
# =========================================================================

class TestBedrockProvider:

    def setup_method(self):
        self.provider = BedrockProvider()

    def test_normalize_request_basic(self):
        """Bedrock Converse format -> ModelRequest."""
        raw = {
            "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
            "messages": [{"role": "user", "content": [{"text": "Hello"}]}],
        }
        req = self.provider.normalize_request(raw)
        assert req.provider == "bedrock"
        assert req.model == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert len(req.messages) == 1
        assert req.messages[0]["role"] == "user"
        assert req.messages[0]["content"] == "Hello"

    def test_normalize_request_with_system(self):
        """System blocks become system messages."""
        raw = {
            "messages": [{"role": "user", "content": [{"text": "Hi"}]}],
            "system": [{"text": "You are a helpful assistant."}],
        }
        req = self.provider.normalize_request(raw)
        assert len(req.messages) == 2
        assert req.messages[0]["role"] == "system"
        assert req.messages[0]["content"] == "You are a helpful assistant."

    def test_normalize_request_with_tools(self):
        """Extracts toolSpec from toolConfig."""
        raw = {
            "messages": [{"role": "user", "content": [{"text": "Search"}]}],
            "toolConfig": {
                "tools": [
                    {"toolSpec": {"name": "search", "description": "Search"}}
                ]
            },
        }
        req = self.provider.normalize_request(raw)
        assert len(req.tool_declarations) == 1
        assert req.tool_declarations[0]["name"] == "search"

    def test_normalize_response_text_only(self):
        """Extracts text from Bedrock response."""
        raw = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello from Bedrock!"}],
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 8, "totalTokens": 18},
            "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
        }
        resp = self.provider.normalize_response(raw)
        assert resp.provider == "bedrock"
        assert resp.text_content == "Hello from Bedrock!"
        assert resp.finish_reason == "end_turn"
        assert resp.token_usage["prompt_tokens"] == 10
        assert resp.token_usage["completion_tokens"] == 8
        assert resp.token_usage["total_tokens"] == 18
        assert len(resp.tool_calls) == 0

    def test_normalize_response_with_tool_use(self):
        """Extracts toolUse from Bedrock response."""
        raw = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "I'll search for that."},
                        {
                            "toolUse": {
                                "toolUseId": "tu-001",
                                "name": "web_search",
                                "input": {"query": "PACT"},
                            }
                        },
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 20, "outputTokens": 15, "totalTokens": 35},
        }
        resp = self.provider.normalize_response(raw)
        assert resp.text_content == "I'll search for that."
        assert resp.finish_reason == "tool_use"
        assert len(resp.tool_calls) == 1
        tc = resp.tool_calls[0]
        assert tc.tool_id == "web_search"
        assert tc.args == {"query": "PACT"}
        assert tc.tool_call_id == "tu-001"

    def test_normalize_response_multiple_tool_uses(self):
        """Handles multiple toolUse blocks."""
        raw = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"toolUse": {"toolUseId": "tu-1", "name": "tool_a", "input": {"x": 1}}},
                        {"toolUse": {"toolUseId": "tu-2", "name": "tool_b", "input": {"y": 2}}},
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 10, "outputTokens": 10, "totalTokens": 20},
        }
        resp = self.provider.normalize_response(raw)
        assert len(resp.tool_calls) == 2
        assert resp.tool_calls[0].tool_call_id == "tu-1"
        assert resp.tool_calls[1].tool_call_id == "tu-2"

    def test_invoke_mock_returns_text(self):
        """Mock invoke returns text when no tools declared."""
        req = ModelRequest(
            provider="bedrock",
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            messages=[{"role": "user", "content": "Hello"}],
        )
        import asyncio
        resp = asyncio.get_event_loop().run_until_complete(self.provider.invoke(req))
        assert resp.provider == "bedrock"
        assert "Mock Bedrock response" in resp.text_content
        assert resp.finish_reason == "end_turn"

    def test_invoke_mock_returns_tool_use(self):
        """Mock invoke returns tool call when tools are declared."""
        req = ModelRequest(
            provider="bedrock",
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            messages=[{"role": "user", "content": "Search for PACT"}],
            tool_declarations=[{"name": "web_search", "description": "Search"}],
        )
        import asyncio
        resp = asyncio.get_event_loop().run_until_complete(self.provider.invoke(req))
        assert resp.provider == "bedrock"
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].tool_id == "web_search"
        assert resp.finish_reason == "tool_use"

    def test_build_request_body(self):
        """_build_request_body produces correct Bedrock format."""
        req = ModelRequest(
            provider="bedrock",
            model="test-model",
            messages=[
                {"role": "system", "content": "Be helpful"},
                {"role": "user", "content": "Hi"},
            ],
            tool_declarations=[{"name": "search"}],
            generation_params={"temperature": 0.7},
        )
        body = self.provider._build_request_body(req)
        assert body["modelId"] == "test-model"
        assert len(body["messages"]) == 1  # system is separate
        assert body["system"] == [{"text": "Be helpful"}]
        assert body["messages"][0]["role"] == "user"
        assert "toolConfig" in body
        assert body["inferenceConfig"]["temperature"] == 0.7


# =========================================================================
# OpenAI-Compatible Provider Tests
# =========================================================================

class TestOpenAICompatibleProvider:

    def setup_method(self):
        self.provider = OpenAICompatibleProvider(api_key="test-key", base_url="http://localhost:8080/v1")

    def test_normalize_request_basic(self):
        """OpenAI chat format -> ModelRequest."""
        raw = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ],
        }
        req = self.provider.normalize_request(raw)
        assert req.provider == "openai"
        assert req.model == "gpt-4o"
        assert len(req.messages) == 2
        assert req.messages[0]["role"] == "system"

    def test_normalize_request_with_tools(self):
        """Extracts function definitions from tools."""
        raw = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Search"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "search",
                        "description": "Search the web",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        }
        req = self.provider.normalize_request(raw)
        assert len(req.tool_declarations) == 1
        assert req.tool_declarations[0]["name"] == "search"

    def test_normalize_request_preserves_generation_params(self):
        """Non-standard keys are captured as generation params."""
        raw = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        req = self.provider.normalize_request(raw)
        assert req.generation_params.get("temperature") == 0.7
        assert req.generation_params.get("max_tokens") == 1024

    def test_normalize_response_text_only(self):
        """Extracts text from OpenAI response."""
        raw = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello there!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        resp = self.provider.normalize_response(raw)
        assert resp.provider == "openai"
        assert resp.text_content == "Hello there!"
        assert resp.finish_reason == "stop"
        assert resp.token_usage["prompt_tokens"] == 10
        assert resp.token_usage["completion_tokens"] == 5
        assert resp.token_usage["total_tokens"] == 15
        assert len(resp.tool_calls) == 0

    def test_normalize_response_with_tool_calls(self):
        """Extracts tool calls from OpenAI response."""
        raw = {
            "id": "chatcmpl-456",
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": '{"query": "PACT"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35},
        }
        resp = self.provider.normalize_response(raw)
        assert resp.finish_reason == "tool_calls"
        assert len(resp.tool_calls) == 1
        tc = resp.tool_calls[0]
        assert tc.tool_id == "web_search"
        assert tc.args == {"query": "PACT"}
        assert tc.tool_call_id == "call_abc"

    def test_normalize_response_multiple_tool_calls(self):
        """Handles multiple tool calls."""
        raw = {
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "tool_a", "arguments": '{"x": 1}'},
                            },
                            {
                                "id": "call_2",
                                "type": "function",
                                "function": {"name": "tool_b", "arguments": '{"y": 2}'},
                            },
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
        resp = self.provider.normalize_response(raw)
        assert len(resp.tool_calls) == 2
        assert resp.tool_calls[0].tool_call_id == "call_1"
        assert resp.tool_calls[1].tool_call_id == "call_2"

    def test_normalize_response_handles_invalid_json_in_tool_args(self):
        """Gracefully handles invalid JSON in tool arguments."""
        raw = {
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_bad",
                                "type": "function",
                                "function": {
                                    "name": "broken",
                                    "arguments": "not-json",
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
        resp = self.provider.normalize_response(raw)
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].args == {}

    def test_normalize_response_empty_choices(self):
        """Handles empty choices."""
        raw = {"model": "gpt-4o", "choices": []}
        resp = self.provider.normalize_response(raw)
        assert resp.text_content == ""
        assert resp.tool_calls == []

    async def test_invoke_makes_http_call(self):
        """invoke() calls the OpenAI-compatible API with correct format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "API response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            req = ModelRequest(
                provider="openai",
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
            )
            resp = await self.provider.invoke(req)

            assert resp.text_content == "API response"
            assert resp.provider == "openai"

            # Verify the HTTP call
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            url = call_args[0][0]
            assert "chat/completions" in url

            # Verify request body
            body = call_args[1]["json"]
            assert body["model"] == "gpt-4o"
            assert len(body["messages"]) == 1

    async def test_invoke_with_tools(self):
        """invoke() sends tools in OpenAI format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"query": "test"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            req = ModelRequest(
                provider="openai",
                model="gpt-4o",
                messages=[{"role": "user", "content": "Search"}],
                tool_declarations=[{"name": "search", "description": "Search"}],
            )
            resp = await self.provider.invoke(req)

            assert len(resp.tool_calls) == 1
            assert resp.tool_calls[0].tool_id == "search"

            body = mock_client.post.call_args[1]["json"]
            assert "tools" in body
            assert body["tools"][0]["type"] == "function"
