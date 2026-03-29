"""File operation tools — read, write, list, and search files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from workclaw.tools.base import Tool, ToolResult


class ReadFileTool(Tool):
    """Read the contents of a file."""

    name = "read_file"
    description = "Read the contents of a file at the given path. Returns the file content as text."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file to read",
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum number of lines to read (default: all)",
            },
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"]).expanduser().resolve()
        max_lines = kwargs.get("max_lines")

        if not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        if not path.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {path}")

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if max_lines:
                lines = content.splitlines()
                content = "\n".join(lines[:max_lines])
                if len(lines) > max_lines:
                    content += f"\n\n... ({len(lines) - max_lines} more lines)"
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(Tool):
    """Write content to a file."""

    name = "write_file"
    description = "Write content to a file, creating parent directories if needed. Overwrites existing content."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["path", "content"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"]).expanduser().resolve()
        content = kwargs["content"]

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} bytes to {path}",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirectoryTool(Tool):
    """List contents of a directory."""

    name = "list_directory"
    description = "List files and directories at the given path. Returns names with type indicators."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the directory to list",
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to list recursively (default: false)",
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum recursion depth (default: 3)",
            },
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"]).expanduser().resolve()
        recursive = kwargs.get("recursive", False)
        max_depth = kwargs.get("max_depth", 3)

        if not path.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        if not path.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {path}")

        try:
            entries = self._list_entries(path, recursive, max_depth, 0)
            output = "\n".join(entries)
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _list_entries(
        self, path: Path, recursive: bool, max_depth: int, current_depth: int
    ) -> list[str]:
        entries = []
        try:
            for item in sorted(path.iterdir()):
                # Skip hidden files and common non-essential dirs
                if item.name.startswith(".") or item.name in {
                    "__pycache__",
                    "node_modules",
                    ".git",
                    "venv",
                    ".venv",
                }:
                    continue

                indent = "  " * current_depth
                if item.is_dir():
                    entries.append(f"{indent}📁 {item.name}/")
                    if recursive and current_depth < max_depth:
                        entries.extend(
                            self._list_entries(item, True, max_depth, current_depth + 1)
                        )
                else:
                    size = item.stat().st_size
                    entries.append(f"{indent}📄 {item.name} ({self._human_size(size)})")
        except PermissionError:
            entries.append(f"{'  ' * current_depth}⛔ Permission denied")
        return entries

    @staticmethod
    def _human_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


class SearchInFilesTool(Tool):
    """Search for text patterns across files."""

    name = "search_in_files"
    description = "Search for a text pattern in files within a directory. Returns matching lines with file paths and line numbers."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to search in",
            },
            "pattern": {
                "type": "string",
                "description": "Text pattern to search for",
            },
            "file_pattern": {
                "type": "string",
                "description": "Glob pattern for files to search (e.g., '*.py'). Default: all files.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default: 50)",
            },
        },
        "required": ["path", "pattern"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"]).expanduser().resolve()
        pattern = kwargs["pattern"]
        file_pattern = kwargs.get("file_pattern", "*")
        max_results = kwargs.get("max_results", 50)

        if not path.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")

        try:
            results = []
            glob_method = path.rglob if path.is_dir() else [path]

            for file_path in (path.rglob(file_pattern) if path.is_dir() else [path]):
                if not file_path.is_file():
                    continue
                # Skip binary files and hidden directories
                if any(p.startswith(".") for p in file_path.parts):
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(content.splitlines(), 1):
                        if pattern.lower() in line.lower():
                            rel_path = file_path.relative_to(path) if path.is_dir() else file_path.name
                            results.append(f"{rel_path}:{i}: {line.strip()}")
                            if len(results) >= max_results:
                                break
                except (UnicodeDecodeError, PermissionError):
                    continue
                if len(results) >= max_results:
                    break

            if not results:
                return ToolResult(success=True, output=f"No matches found for '{pattern}'")

            output = f"Found {len(results)} matches:\n\n" + "\n".join(results)
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
