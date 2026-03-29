"""File-based storage layer for WorkClaw — conversations, memory, and reports."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


class FileStore:
    """Simple file-based storage using YAML, JSON, and Markdown.

    Data is organized into collections (subdirectories) under the data root.
    Each entry is a file identified by its key.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _collection_dir(self, collection: str) -> Path:
        """Get the directory for a collection, creating if needed."""
        path = self.data_dir / collection
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_yaml(self, collection: str, key: str, data: dict[str, Any]) -> Path:
        """Save data as a YAML file."""
        path = self._collection_dir(collection) / f"{key}.yaml"
        data["_updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        logger.debug(f"Saved YAML: {path}")
        return path

    def load_yaml(self, collection: str, key: str) -> Optional[dict[str, Any]]:
        """Load data from a YAML file."""
        path = self._collection_dir(collection) / f"{key}.yaml"
        if not path.exists():
            return None
        with open(path) as f:
            return yaml.safe_load(f) or {}

    def save_json(self, collection: str, key: str, data: Any) -> Path:
        """Save data as a JSON file."""
        path = self._collection_dir(collection) / f"{key}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug(f"Saved JSON: {path}")
        return path

    def load_json(self, collection: str, key: str) -> Optional[Any]:
        """Load data from a JSON file."""
        path = self._collection_dir(collection) / f"{key}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def save_markdown(self, collection: str, key: str, content: str) -> Path:
        """Save content as a Markdown file."""
        path = self._collection_dir(collection) / f"{key}.md"
        with open(path, "w") as f:
            f.write(content)
        logger.debug(f"Saved Markdown: {path}")
        return path

    def load_markdown(self, collection: str, key: str) -> Optional[str]:
        """Load content from a Markdown file."""
        path = self._collection_dir(collection) / f"{key}.md"
        if not path.exists():
            return None
        with open(path) as f:
            return f.read()

    def list_keys(self, collection: str, suffix: str = "") -> list[str]:
        """List all keys in a collection, optionally filtered by suffix."""
        col_dir = self._collection_dir(collection)
        keys = []
        for p in sorted(col_dir.iterdir()):
            if p.is_file() and (not suffix or p.suffix == suffix):
                keys.append(p.stem)
        return keys

    def delete(self, collection: str, key: str) -> bool:
        """Delete an entry from a collection."""
        col_dir = self._collection_dir(collection)
        deleted = False
        for ext in [".yaml", ".json", ".md"]:
            path = col_dir / f"{key}{ext}"
            if path.exists():
                path.unlink()
                deleted = True
                logger.debug(f"Deleted: {path}")
        return deleted

    def search(self, collection: str, query: str) -> list[dict[str, Any]]:
        """Simple text search across a collection's YAML/JSON files."""
        results = []
        col_dir = self._collection_dir(collection)

        for path in col_dir.iterdir():
            if not path.is_file():
                continue
            try:
                content = path.read_text()
                if query.lower() in content.lower():
                    results.append(
                        {
                            "key": path.stem,
                            "path": str(path),
                            "type": path.suffix,
                        }
                    )
            except Exception:
                continue

        return results
