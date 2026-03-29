"""Shared test fixtures for WorkClaw tests."""

import pytest
from pathlib import Path

from workclaw.config.settings import WorkClawSettings, LLMProvider
from workclaw.storage.store import FileStore
from workclaw.core.memory import Memory
from workclaw.tools.registry import ToolRegistry
from workclaw.tools.file_ops import ReadFileTool, WriteFileTool, ListDirectoryTool, SearchInFilesTool


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def settings(tmp_data_dir, tmp_path):
    """Test settings with temporary directories."""
    return WorkClawSettings(
        llm_provider=LLMProvider.OPENAI,
        llm_model="gpt-4o",
        data_dir=tmp_data_dir,
        workspace_dir=tmp_path / "workspaces",
    )


@pytest.fixture
def store(tmp_data_dir):
    """File store with temp directory."""
    return FileStore(tmp_data_dir)


@pytest.fixture
def memory(store):
    """Memory instance with temp store."""
    return Memory(store)


@pytest.fixture
def tool_registry():
    """Tool registry with file tools registered."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ListDirectoryTool())
    registry.register(SearchInFilesTool())
    return registry
