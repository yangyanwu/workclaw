"""Persistent memory for the WorkClaw agent — file-based conversation and fact storage."""

from __future__ import annotations

import logging
from typing import Any, Optional

from workclaw.storage.store import FileStore

logger = logging.getLogger(__name__)


class Memory:
    """Agent memory backed by file storage.

    Stores:
    - Conversations (chat history)
    - Facts (learned project/user preferences)
    - Context snippets (reusable knowledge)
    """

    def __init__(self, store: FileStore) -> None:
        self.store = store

    # --- Conversations ---

    def save_conversation(self, conv_id: str, data: dict[str, Any]) -> None:
        """Save a conversation to storage."""
        self.store.save_json("conversations", conv_id, data)

    def load_conversation(self, conv_id: str) -> Optional[dict[str, Any]]:
        """Load a conversation from storage."""
        return self.store.load_json("conversations", conv_id)

    def list_conversations(self) -> list[dict[str, str]]:
        """List all saved conversations with their titles."""
        conversations = []
        for key in self.store.list_keys("conversations", suffix=".json"):
            data = self.store.load_json("conversations", key)
            if data:
                conversations.append(
                    {
                        "id": data.get("id", key),
                        "title": data.get("title", "Untitled"),
                        "created_at": data.get("created_at", ""),
                    }
                )
        # Sort by creation date, newest first
        conversations.sort(key=lambda c: c.get("created_at", ""), reverse=True)
        return conversations

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation."""
        return self.store.delete("conversations", conv_id)

    # --- Facts (persistent knowledge) ---

    def save_fact(self, key: str, value: Any) -> None:
        """Save a fact/preference that the agent has learned."""
        facts = self.store.load_yaml("memory", "facts") or {"facts": {}}
        facts["facts"][key] = value
        self.store.save_yaml("memory", "facts", facts)

    def get_fact(self, key: str) -> Optional[Any]:
        """Retrieve a specific fact."""
        facts = self.store.load_yaml("memory", "facts")
        if facts:
            return facts.get("facts", {}).get(key)
        return None

    def get_all_facts(self) -> dict[str, Any]:
        """Get all stored facts."""
        facts = self.store.load_yaml("memory", "facts")
        if facts:
            return facts.get("facts", {})
        return {}

    # --- Context Retrieval ---

    def get_relevant_context(self, query: str) -> Optional[str]:
        """Get relevant memory context for a query.

        This is a simple implementation that returns stored facts.
        Could be enhanced with vector search in the future.
        """
        facts = self.get_all_facts()
        if not facts:
            return None

        # Build a context string from facts
        context_parts = []
        for key, value in facts.items():
            context_parts.append(f"- {key}: {value}")

        if context_parts:
            return "Known facts:\n" + "\n".join(context_parts)
        return None

    # --- Analysis Reports ---

    def save_analysis_report(self, report_id: str, report: dict[str, Any]) -> None:
        """Save a code analysis report."""
        self.store.save_json("analysis_reports", report_id, report)

    def load_analysis_report(self, report_id: str) -> Optional[dict[str, Any]]:
        """Load a code analysis report."""
        return self.store.load_json("analysis_reports", report_id)

    def list_analysis_reports(self) -> list[str]:
        """List all analysis report keys."""
        return self.store.list_keys("analysis_reports", suffix=".json")
