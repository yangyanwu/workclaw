"""Abstract base class for all WorkClaw integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Integration(ABC):
    """Base class for external service integrations (GitHub, Jira, Bitbucket, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Integration name for display and logging."""
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """Initialize the connection. Returns True if successful."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the integration is healthy and accessible."""
        ...

    async def disconnect(self) -> None:
        """Clean up resources. Override if needed."""
        pass
