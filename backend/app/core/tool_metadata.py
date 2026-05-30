"""Tool metadata Pydantic model for PACT tool registry."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SideEffect(str, Enum):
    """Side effect classification for tools."""
    NONE = "none"
    READ = "read"
    INTERNAL_WRITE = "internal_write"
    EXTERNAL_WRITE = "external_write"
    DELETE = "delete"
    PAYMENT = "payment"
    SHELL = "shell"
    NETWORK = "network"
    PRIVILEGED = "privileged"


class ToolMetadata(BaseModel):
    """Metadata for a registered PACT tool."""

    tool_id: str
    display_name: str
    version: str = "1.0.0"
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    side_effect: SideEffect = SideEffect.NONE
    resource_type: str = "default"
    resource_extractor: dict[str, Any] = Field(default_factory=dict)
    output_provenance: list[str] = Field(default_factory=list)
    sensitivity: str = "low"
    default_requires_approval: bool = False
