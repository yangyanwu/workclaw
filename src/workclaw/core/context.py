"""Context assembly for LLM calls — manages system prompt, history, and memory."""

from __future__ import annotations

from typing import Any, Optional

from workclaw.config.settings import WorkClawSettings


class ContextAssembler:
    """Builds the message list for LLM calls.

    Manages token budget by trimming older messages when
    the conversation grows too long.
    """

    def __init__(self, settings: WorkClawSettings) -> None:
        self.settings = settings
        self.max_context_tokens = settings.agent_max_context_tokens
        # Rough estimate: 1 token ≈ 4 chars
        self.chars_per_token = 4

    def build_messages(
        self,
        system_prompt: str,
        conversation_messages: list[dict[str, Any]],
        memory_context: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Build the full message list for an LLM call.

        Structure:
        1. System prompt (with optional memory context appended)
        2. Conversation history (trimmed if too long)
        """
        messages: list[dict[str, Any]] = []

        # System message with optional memory context
        system_content = system_prompt
        if memory_context:
            system_content += (
                f"\n\n## Relevant Context from Memory\n{memory_context}"
            )

        messages.append({"role": "system", "content": system_content})

        # Add conversation messages, trimming old ones if needed
        trimmed = self._trim_history(
            conversation_messages,
            budget_chars=self.max_context_tokens * self.chars_per_token
            - len(system_content),
        )
        messages.extend(trimmed)

        return messages

    def _trim_history(
        self,
        messages: list[dict[str, Any]],
        budget_chars: int,
    ) -> list[dict[str, Any]]:
        """Keep the most recent messages that fit within the token budget.

        Always keeps the first user message for context, then fills
        from the most recent messages backwards.
        """
        if not messages:
            return []

        # Calculate total size
        total_chars = sum(self._message_chars(m) for m in messages)

        if total_chars <= budget_chars:
            return messages

        # Keep first message + as many recent messages as fit
        result = []
        first_message = messages[0]
        remaining_budget = budget_chars - self._message_chars(first_message)

        # Work backwards from the end
        recent = []
        for msg in reversed(messages[1:]):
            msg_size = self._message_chars(msg)
            if remaining_budget - msg_size > 0:
                recent.append(msg)
                remaining_budget -= msg_size
            else:
                break

        result.append(first_message)
        if len(recent) < len(messages) - 1:
            result.append(
                {
                    "role": "system",
                    "content": f"[{len(messages) - 1 - len(recent)} earlier messages trimmed for context window]",
                }
            )
        result.extend(reversed(recent))
        return result

    @staticmethod
    def _message_chars(message: dict[str, Any]) -> int:
        """Estimate the character count of a message."""
        content = message.get("content", "")
        if isinstance(content, str):
            return len(content)
        return 0
