"""Bedrock Converse API provider adapter."""

from __future__ import annotations

import os
from typing import Optional

from app.adapters.providers.base import ModelProvider, ModelRequest, ModelResponse, ToolCall


class BedrockProvider(ModelProvider):
    """AWS Bedrock Converse API provider adapter.

    Note: The invoke() method is currently MOCKED — it returns a synthetic
    response instead of calling AWS.  Replace the _call_bedrock helper when
    real AWS credentials are available.
    """

    name = "bedrock"

    def __init__(
        self,
        region: Optional[str] = None,
        model_id: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
        self.access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "")
        self.secret_access_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "")

    # ------------------------------------------------------------------
    # normalize_request: Bedrock Converse format -> ModelRequest
    # ------------------------------------------------------------------
    def normalize_request(self, raw: dict) -> ModelRequest:
        """Convert a Bedrock Converse request to a ModelRequest.

        Bedrock format:
        {
            "modelId": "...",
            "messages": [{"role": "user", "content": [{"text": "..."}]}],
            "system": [{"text": "..."}],
            "toolConfig": {"tools": [{"toolSpec": {...}}]},
            "inferenceConfig": {"temperature": 0.7, "maxTokens": 1024}
        }
        """
        messages: list[dict] = []

        # System messages
        for sys_block in raw.get("system", []):
            if isinstance(sys_block, dict) and "text" in sys_block:
                messages.append({"role": "system", "content": sys_block["text"]})
            elif isinstance(sys_block, str):
                messages.append({"role": "system", "content": sys_block})

        # Conversation messages
        for msg in raw.get("messages", []):
            role = msg.get("role", "user")
            content_parts = msg.get("content", [])
            text_parts: list[str] = []
            for part in content_parts:
                if isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
                elif isinstance(part, str):
                    text_parts.append(part)
            messages.append({"role": role, "content": " ".join(text_parts)})

        tool_declarations: list[dict] = []
        tool_config = raw.get("toolConfig", {})
        for tool in tool_config.get("tools", []):
            spec = tool.get("toolSpec", {})
            if spec:
                tool_declarations.append(spec)

        inference_config = raw.get("inferenceConfig", {})

        return ModelRequest(
            provider="bedrock",
            model=raw.get("modelId", self.model_id),
            messages=messages,
            tool_declarations=tool_declarations,
            generation_params=inference_config,
            metadata=raw.get("metadata", {}),
            run_id=raw.get("run_id"),
            agent_id=raw.get("agent_id"),
            intent_hash=raw.get("intent_hash"),
        )

    # ------------------------------------------------------------------
    # normalize_response: Bedrock Converse response -> ModelResponse
    # ------------------------------------------------------------------
    def normalize_response(self, raw: dict) -> ModelResponse:
        """Convert a Bedrock Converse response to a ModelResponse.

        Bedrock response:
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "..."}, {"toolUse": {"toolUseId": "...", "name": "...", "input": {...}}}]
                }
            },
            "stopReason": "end_turn" | "tool_use",
            "usage": {"inputTokens": N, "outputTokens": N, "totalTokens": N}
        }
        """
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        finish_reason = raw.get("stopReason")

        output = raw.get("output", {})
        message = output.get("message", {})
        for part in message.get("content", []):
            if "text" in part:
                text_parts.append(part["text"])
            if "toolUse" in part:
                tu = part["toolUse"]
                tool_calls.append(
                    ToolCall(
                        tool_id=tu.get("name", ""),
                        args=tu.get("input", {}),
                        tool_call_id=tu.get("toolUseId"),
                    )
                )

        usage = raw.get("usage", {})
        token_usage = None
        if usage:
            token_usage = {
                "prompt_tokens": usage.get("inputTokens", 0),
                "completion_tokens": usage.get("outputTokens", 0),
                "total_tokens": usage.get("totalTokens", 0),
            }

        return ModelResponse(
            provider="bedrock",
            model=raw.get("modelId", self.model_id),
            raw_response=raw,
            text_content=" ".join(text_parts),
            tool_calls=tool_calls,
            token_usage=token_usage,
            safety_ratings=None,
            finish_reason=finish_reason,
        )

    # ------------------------------------------------------------------
    # invoke: call Bedrock (currently mocked)
    # ------------------------------------------------------------------
    async def invoke(self, request: ModelRequest) -> ModelResponse:
        """Send a request to Bedrock Converse API.

        CURRENTLY MOCKED — returns a synthetic response instead of calling AWS.
        Replace _call_bedrock() with a real boto3 call when credentials are available.
        """
        body = self._build_request_body(request)
        raw = self._call_bedrock_mock(body, request)
        return self.normalize_response(raw)

    def _build_request_body(self, request: ModelRequest) -> dict:
        """Build the Bedrock Converse request body from a ModelRequest."""
        messages: list[dict] = []
        system_blocks: list[dict] = []

        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_blocks.append({"text": content})
            else:
                messages.append({"role": role, "content": [{"text": content}]})

        body: dict = {
            "modelId": request.model,
            "messages": messages,
        }
        if system_blocks:
            body["system"] = system_blocks

        if request.tool_declarations:
            body["toolConfig"] = {
                "tools": [{"toolSpec": decl} for decl in request.tool_declarations]
            }

        if request.generation_params:
            body["inferenceConfig"] = request.generation_params

        return body

    def _call_bedrock_mock(self, body: dict, request: ModelRequest) -> dict:
        """Return a mock Bedrock Converse response."""
        # Simulate: if there are tool declarations and user asks about tools,
        # return a tool use; otherwise return text.
        has_tools = bool(request.tool_declarations)

        # Simulate a simple assistant text response
        last_user_msg = ""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break

        if has_tools and request.tool_declarations:
            # Return a tool call for the first declared tool
            first_tool = request.tool_declarations[0]
            tool_name = first_tool.get("name", "unknown")
            return {
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"text": f"I'll use the {tool_name} tool."},
                            {
                                "toolUse": {
                                    "toolUseId": "mock-tool-use-001",
                                    "name": tool_name,
                                    "input": {"query": last_user_msg[:100]},
                                }
                            },
                        ],
                    }
                },
                "stopReason": "tool_use",
                "usage": {"inputTokens": 50, "outputTokens": 30, "totalTokens": 80},
                "modelId": request.model,
            }

        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": f"Mock Bedrock response to: {last_user_msg[:100]}"}],
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 50, "outputTokens": 20, "totalTokens": 70},
            "modelId": request.model,
        }
