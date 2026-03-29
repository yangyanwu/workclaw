"""Tests for the file-based storage layer."""

import pytest

from workclaw.storage.store import FileStore


def test_save_and_load_yaml(store):
    """Test saving and loading YAML data."""
    data = {"name": "test", "value": 42, "nested": {"key": "val"}}
    store.save_yaml("test_collection", "item1", data)

    loaded = store.load_yaml("test_collection", "item1")
    assert loaded is not None
    assert loaded["name"] == "test"
    assert loaded["value"] == 42
    assert loaded["nested"]["key"] == "val"


def test_save_and_load_json(store):
    """Test saving and loading JSON data."""
    data = {"items": [1, 2, 3], "active": True}
    store.save_json("test_json", "item1", data)

    loaded = store.load_json("test_json", "item1")
    assert loaded is not None
    assert loaded["items"] == [1, 2, 3]
    assert loaded["active"] is True


def test_save_and_load_markdown(store):
    """Test saving and loading Markdown content."""
    content = "# Test\n\nHello world"
    store.save_markdown("docs", "readme", content)

    loaded = store.load_markdown("docs", "readme")
    assert loaded == content


def test_list_keys(store):
    """Test listing keys in a collection."""
    store.save_yaml("items", "alpha", {"v": 1})
    store.save_yaml("items", "beta", {"v": 2})
    store.save_yaml("items", "gamma", {"v": 3})

    keys = store.list_keys("items", suffix=".yaml")
    assert sorted(keys) == ["alpha", "beta", "gamma"]


def test_delete(store):
    """Test deleting an entry."""
    store.save_yaml("items", "to_delete", {"v": 1})
    assert store.load_yaml("items", "to_delete") is not None

    deleted = store.delete("items", "to_delete")
    assert deleted is True
    assert store.load_yaml("items", "to_delete") is None


def test_search(store):
    """Test searching across a collection."""
    store.save_yaml("search", "item1", {"content": "hello world"})
    store.save_yaml("search", "item2", {"content": "goodbye world"})
    store.save_yaml("search", "item3", {"content": "hello there"})

    results = store.search("search", "hello")
    assert len(results) == 2


def test_load_nonexistent(store):
    """Test loading a key that doesn't exist."""
    assert store.load_yaml("collection", "nonexistent") is None
    assert store.load_json("collection", "nonexistent") is None
    assert store.load_markdown("collection", "nonexistent") is None


def test_tool_registry():
    """Test the tool registry."""
    from workclaw.tools.registry import ToolRegistry
    from workclaw.tools.file_ops import ReadFileTool, WriteFileTool

    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())

    assert len(registry) == 2
    assert "read_file" in registry
    assert "write_file" in registry

    tool = registry.get("read_file")
    assert tool is not None
    assert tool.name == "read_file"

    tools = registry.to_openai_tools()
    assert len(tools) == 2
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] in ["read_file", "write_file"]


@pytest.mark.asyncio
async def test_read_file_tool(tmp_path):
    """Test the read_file tool."""
    from workclaw.tools.file_ops import ReadFileTool

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, WorkClaw!")

    tool = ReadFileTool()
    result = await tool.execute(path=str(test_file))

    assert result.success is True
    assert "Hello, WorkClaw!" in result.output


@pytest.mark.asyncio
async def test_read_file_not_found():
    """Test read_file with nonexistent file."""
    from workclaw.tools.file_ops import ReadFileTool

    tool = ReadFileTool()
    result = await tool.execute(path="/nonexistent/file.txt")

    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_write_file_tool(tmp_path):
    """Test the write_file tool."""
    from workclaw.tools.file_ops import WriteFileTool

    target = tmp_path / "output" / "test.txt"
    tool = WriteFileTool()
    result = await tool.execute(path=str(target), content="Written by WorkClaw")

    assert result.success is True
    assert target.exists()
    assert target.read_text() == "Written by WorkClaw"


@pytest.mark.asyncio
async def test_list_directory_tool(tmp_path):
    """Test the list_directory tool."""
    from workclaw.tools.file_ops import ListDirectoryTool

    # Create some files
    (tmp_path / "file1.py").write_text("print('hello')")
    (tmp_path / "file2.js").write_text("console.log('hello')")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.txt").write_text("nested")

    tool = ListDirectoryTool()
    result = await tool.execute(path=str(tmp_path))

    assert result.success is True
    assert "file1.py" in result.output
    assert "file2.js" in result.output
    assert "subdir" in result.output
