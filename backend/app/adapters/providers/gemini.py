"""Gemini provider adapter — implements the Google Gemini generateContent API."""

from __future__ import annotations

import os
from typing import Optional

import httpx

from app.adapters.providers.base import ModelProvider, ModelRequest, ModelResponse, ToolCall


class GeminiProvider(ModelProvider):
    """Google Gemini API provider adapter."""

    name = "gemini"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        self.default_model = os.getenv("GEMINI_MODEL") or os.getenv("GOOGLE_MODEL", "gemini-pro")
        self.base_url = (
            base_url
            or os.getenv("GEMINI_API_URL", "https://generativelanguage.googleapis.com")
        )

    # ------------------------------------------------------------------
    # normalize_request: Gemini generateContent format -> ModelRequest
    # ------------------------------------------------------------------
    def normalize_request(self, raw: dict) -> ModelRequest:
        """Convert a Gemini generateContent request to a ModelRequest.

        Gemini format:
        {
            "contents": [{"role": "user", "parts": [{"text": "..."}]}],
            "tools": [{"functionDeclarations": [...]}],
            "generationConfig": {"temperature": 0.7, ...}
        }
        """
        messages: list[dict] = []
        if "messages" in raw:
            for msg in raw.get("messages", []):
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and "text" in part
                    ]
                    content = " ".join(text_parts)
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": str(content),
                })
        else:
            for content in raw.get("contents", []):
                role = content.get("role", "user")
                parts = content.get("parts", [])
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                messages.append({"role": role, "content": " ".join(text_parts)})

        tool_declarations: list[dict] = []
        for tool_block in raw.get("tools", []):
            for decl in tool_block.get("functionDeclarations", []):
                tool_declarations.append(decl)

        gen_config = raw.get("generationConfig", {})

        return ModelRequest(
            provider="gemini",
            model=raw.get("model", self.default_model),
            messages=messages,
            tool_declarations=tool_declarations,
            generation_params=gen_config,
            metadata=raw.get("metadata", {}),
            run_id=raw.get("run_id"),
            agent_id=raw.get("agent_id"),
            intent_hash=raw.get("intent_hash"),
        )

    # ------------------------------------------------------------------
    # normalize_response: Gemini response -> ModelResponse
    # ------------------------------------------------------------------
    def normalize_response(self, raw: dict) -> ModelResponse:
        """Convert a Gemini generateContent response to a ModelResponse.

        Gemini response:
        {
            "candidates": [{
                "content": {"parts": [{"text": "..."}, {"functionCall": {...}}]},
                "finishReason": "..."
            }],
            "usageMetadata": {"promptTokenCount": N, "candidatesTokenCount": N, "totalTokenCount": N}
        }
        """
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        safety_ratings: Optional[list[dict]] = None
        finish_reason: Optional[str] = None

        candidates = raw.get("candidates", [])
        if candidates:
            candidate = candidates[0]
            content = candidate.get("content", {})
            finish_reason = candidate.get("finishReason")

            for part in content.get("parts", []):
                if "text" in part:
                    text_parts.append(part["text"])
                if "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append(
                        ToolCall(
                            tool_id=fc.get("name", ""),
                            args=fc.get("args", {}),
                        )
                    )

            safety_ratings = candidate.get("safetyLabels") or candidate.get("safetyRatings")

        usage = raw.get("usageMetadata", {})
        token_usage = None
        if usage:
            token_usage = {
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0),
            }

        return ModelResponse(
            provider="gemini",
            model=raw.get("model", self.default_model),
            raw_response=raw,
            text_content=" ".join(text_parts),
            tool_calls=tool_calls,
            token_usage=token_usage,
            safety_ratings=safety_ratings,
            finish_reason=finish_reason,
        )

    # ------------------------------------------------------------------
    # invoke: call the Gemini API
    # ------------------------------------------------------------------
    async def invoke(self, request: ModelRequest) -> ModelResponse:
        """Send a request to the Gemini API and return a normalized response."""
        if not self.api_key:
            raise ValueError("Gemini API key is not configured")

        # Build Gemini request from normalized ModelRequest
        contents: list[dict] = []
        system_instruction = None

        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})

        body: dict = {"contents": contents}

        if system_instruction:
            body["systemInstruction"] = system_instruction

        if request.tool_declarations:
            body["tools"] = [{"functionDeclarations": request.tool_declarations}]

        if request.generation_params:
            body["generationConfig"] = request.generation_params

        model = request.model
        url = f"{self.base_url}/v1beta/models/{model}:generateContent"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            raw = resp.json()

        raw.setdefault("model", model)
        return self.normalize_response(raw)
