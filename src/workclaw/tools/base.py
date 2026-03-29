"""Abstract base class for all WorkClaw tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: str
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """Abstract base class for agent tools.

    Each tool provides a name, description, and JSON Schema parameters
    so the LLM knows how to call it.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name (used in LLM function calling)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for the tool's parameters."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given arguments."""
        ...

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
