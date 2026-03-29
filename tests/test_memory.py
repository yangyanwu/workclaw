"""Tests for the memory system."""

import pytest

from workclaw.core.memory import Memory
from workclaw.storage.store import FileStore


def test_save_and_load_conversation(store):
    """Test saving and loading a conversation."""
    memory = Memory(store)

    conv_data = {
        "id": "test123",
        "title": "Test Conversation",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        "created_at": "2026-03-29T00:00:00Z",
    }

    memory.save_conversation("test123", conv_data)
    loaded = memory.load_conversation("test123")

    assert loaded is not None
    assert loaded["id"] == "test123"
    assert loaded["title"] == "Test Conversation"
    assert len(loaded["messages"]) == 2


def test_list_conversations(store):
    """Test listing conversations."""
    memory = Memory(store)

    memory.save_conversation("conv1", {
        "id": "conv1", "title": "First", "messages": [], "created_at": "2026-03-29T01:00:00Z"
    })
    memory.save_conversation("conv2", {
        "id": "conv2", "title": "Second", "messages": [], "created_at": "2026-03-29T02:00:00Z"
    })

    conversations = memory.list_conversations()
    assert len(conversations) == 2
    # Should be sorted newest first
    assert conversations[0]["title"] == "Second"


def test_delete_conversation(store):
    """Test deleting a conversation."""
    memory = Memory(store)

    memory.save_conversation("to_delete", {
        "id": "to_delete", "title": "Delete Me", "messages": [], "created_at": "2026-03-29T00:00:00Z"
    })
    assert memory.load_conversation("to_delete") is not None

    memory.delete_conversation("to_delete")
    assert memory.load_conversation("to_delete") is None


def test_save_and_get_fact(store):
    """Test saving and retrieving facts."""
    memory = Memory(store)

    memory.save_fact("preferred_language", "python")
    memory.save_fact("project_name", "WorkClaw")

    assert memory.get_fact("preferred_language") == "python"
    assert memory.get_fact("project_name") == "WorkClaw"
    assert memory.get_fact("nonexistent") is None


def test_get_all_facts(store):
    """Test getting all stored facts."""
    memory = Memory(store)

    memory.save_fact("key1", "value1")
    memory.save_fact("key2", "value2")

    facts = memory.get_all_facts()
    assert facts["key1"] == "value1"
    assert facts["key2"] == "value2"


def test_relevant_context(store):
    """Test getting relevant context from memory."""
    memory = Memory(store)

    # No facts = no context
    assert memory.get_relevant_context("test") is None

    # With facts
    memory.save_fact("language", "python")
    context = memory.get_relevant_context("anything")
    assert context is not None
    assert "python" in context
