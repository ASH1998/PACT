"""OpenAI-compatible provider adapter — works with any provider using the
OpenAI /v1/chat/completions format (e.g. OpenAI, Azure OpenAI, Ollama, vLLM)."""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx

from app.adapters.providers.base import ModelProvider, ModelRequest, ModelResponse, ToolCall


class OpenAICompatibleProvider(ModelProvider):
    """OpenAI-compatible API provider adapter."""

    name = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (
            base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")

    # ------------------------------------------------------------------
    # normalize_request: OpenAI chat format -> ModelRequest
    # ------------------------------------------------------------------
    def normalize_request(self, raw: dict) -> ModelRequest:
        """Convert an OpenAI /v1/chat/completions request to a ModelRequest.

        OpenAI format:
        {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "..."}],
            "tools": [{"type": "function", "function": {"name": "...", ...}}],
            "temperature": 0.7,
            "max_tokens": 1024
        }
        """
        messages = raw.get("messages", [])

        tool_declarations: list[dict] = []
        for tool in raw.get("tools", []):
            if tool.get("type") == "function":
                tool_declarations.append(tool.get("function", {}))

        # Extract generation params (exclude messages, model, tools)
        skip_keys = {"messages", "model", "tools", "metadata", "run_id", "agent_id", "intent_hash"}
        generation_params = {k: v for k, v in raw.items() if k not in skip_keys}

        return ModelRequest(
            provider="openai",
            model=raw.get("model", "gpt-4o"),
            messages=messages,
            tool_declarations=tool_declarations,
            generation_params=generation_params,
            metadata=raw.get("metadata", {}),
            run_id=raw.get("run_id"),
            agent_id=raw.get("agent_id"),
            intent_hash=raw.get("intent_hash"),
        )

    # ------------------------------------------------------------------
    # normalize_response: OpenAI response -> ModelResponse
    # ------------------------------------------------------------------
    def normalize_response(self, raw: dict) -> ModelResponse:
        """Convert an OpenAI /v1/chat/completions response to a ModelResponse.

        OpenAI response:
        {
            "id": "...",
            "choices": [{
                "message": {"role": "assistant", "content": "...", "tool_calls": [...]},
                "finish_reason": "stop" | "tool_calls"
            }],
            "usage": {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
        }
        """
        text_content = ""
        tool_calls: list[ToolCall] = []
        finish_reason = None

        choices = raw.get("choices", [])
        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            text_content = message.get("content", "") or ""
            finish_reason = choice.get("finish_reason")

            for tc in message.get("tool_calls", []):
                func = tc.get("function", {})
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    ToolCall(
                        tool_id=func.get("name", ""),
                        args=args,
                        tool_call_id=tc.get("id"),
                    )
                )

        usage = raw.get("usage", {})
        token_usage = None
        if usage:
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }

        return ModelResponse(
            provider="openai",
            model=raw.get("model", ""),
            raw_response=raw,
            text_content=text_content,
            tool_calls=tool_calls,
            token_usage=token_usage,
            safety_ratings=None,
            finish_reason=finish_reason,
        )

    # ------------------------------------------------------------------
    # invoke: call the OpenAI-compatible API
    # ------------------------------------------------------------------
    async def invoke(self, request: ModelRequest) -> ModelResponse:
        """Send a request to an OpenAI-compatible API and return a normalized response."""
        # Build OpenAI request from normalized ModelRequest
        messages: list[dict] = []
        for msg in request.messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        body: dict = {
            "model": request.model,
            "messages": messages,
        }

        # Add tools in OpenAI function-calling format
        if request.tool_declarations:
            body["tools"] = [
                {"type": "function", "function": decl}
                for decl in request.tool_declarations
            ]

        # Add generation params (temperature, max_tokens, etc.)
        body.update(request.generation_params)

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/chat/completions"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=body,
                headers=headers,
                timeout=60.0,
            )
            resp.raise_for_status()
            raw = resp.json()

        return self.normalize_response(raw)
