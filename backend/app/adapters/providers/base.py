"""Base provider interface — defines the contract for all LLM provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class ModelRequest(BaseModel):
    """Normalized request sent to any LLM provider."""

    provider: str
    model: str
    messages: list[dict]  # [{role: 'user'|'system'|'assistant', content: '...'}]
    tool_declarations: list[dict] = []
    generation_params: dict = {}  # temperature, max_tokens, etc.
    metadata: dict = {}
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    intent_hash: Optional[str] = None


class ToolCall(BaseModel):
    """A tool/function call extracted from a model response."""

    tool_id: str
    args: dict
    tool_call_id: Optional[str] = None


class ModelResponse(BaseModel):
    """Normalized response from any LLM provider."""

    provider: str
    model: str
    raw_response: dict  # Full provider response
    text_content: str = ""  # Text part of response
    tool_calls: list[ToolCall] = []
    token_usage: Optional[dict] = None  # {prompt_tokens, completion_tokens, total_tokens}
    safety_ratings: Optional[list[dict]] = None
    finish_reason: Optional[str] = None


class ModelProvider(ABC):
    """Abstract base class for LLM provider adapters."""

    name: str

    @abstractmethod
    async def invoke(self, request: ModelRequest) -> ModelResponse:
        """Send request to model provider and return normalized response."""
        ...

    @abstractmethod
    def normalize_request(self, raw: dict) -> ModelRequest:
        """Convert provider-specific request format to ModelRequest."""
        ...

    @abstractmethod
    def normalize_response(self, raw: dict) -> ModelResponse:
        """Convert provider-specific response to ModelResponse."""
        ...
