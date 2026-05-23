from __future__ import annotations
"""Base class for mock PACT tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Result from a mock tool execution."""

    success: bool
    tool: str
    output: str
    output_label: str  # provenance label for the output
    side_effect: str | None  # provenance label for side effects, if any


class BaseTool(ABC):
    """Abstract base for mock tools."""

    name: str = "unknown"

    @abstractmethod
    def execute(self, args: dict, seed_data: dict | None = None) -> ToolResult:
        """Execute the tool with given args. Returns a ToolResult."""
        ...
