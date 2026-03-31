"""Pydantic models for project configuration — repos, auth, and scheduling."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


class AuthMethod(StrEnum):
    """Supported authentication methods for git clone."""

    HTTPS = "https"
    HTTPS_CREDENTIALS = "https_credentials"
    SSH_KEY = "ssh_key"
    SSH_AGENT = "ssh_agent"


class RepoSource(BaseModel):
    """A single repository source within a project."""

    url: str  # git@... or https://...
    provider: Literal["github", "bitbucket", "other"] = "other"
    branch: str | None = None
    auth_method: AuthMethod = AuthMethod.HTTPS
    ssh_key_path: Path | None = None  # for SSH_KEY
    username: str | None = None  # for HTTPS_CREDENTIALS
    password_env_var: str | None = None  # env var name holding password
    name: str | None = None  # auto-derived from URL if omitted

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Repository URL cannot be empty")
        # Accept both SSH (git@host:owner/repo) and HTTPS URLs
        if not (v.startswith("git@") or v.startswith("https://") or v.startswith("http://")):
            raise ValueError("URL must be SSH (git@...) or HTTPS (https://...)")
        return v

    @model_validator(mode="after")
    def resolve_name(self) -> RepoSource:
        if self.name is None:
            self.name = self._derive_name()
        return self

    @model_validator(mode="after")
    def resolve_auth(self) -> RepoSource:
        """Auto-detect auth method from URL if left as default HTTPS."""
        if self.auth_method == AuthMethod.HTTPS and self.url.startswith("git@"):
            self.auth_method = AuthMethod.SSH_AGENT
        return self

    def _derive_name(self) -> str:
        """Derive repo name from URL (e.g., 'owner/repo' or just 'repo')."""
        url = self.url
        if url.startswith("git@"):
            # git@github.com:owner/repo.git -> owner/repo
            match = re.match(r"git@[^:]+:(.+?)(?:\.git)?$", url)
            if match:
                return match.group(1)
        else:
            parsed = urlparse(url)
            path = parsed.path.strip("/").removesuffix(".git")
            if path:
                return path
        return url


class ProjectConfig(BaseModel):
    """Configuration for a multi-repository project."""

    name: str
    description: str = ""
    repos: list[RepoSource] = Field(default_factory=list)
    analysis_max_files_per_repo: int = 20
    analysis_focus_areas: list[str] | None = None
    schedule_cron: str | None = None  # e.g. "0 2 * * 1"
    created_at: str | None = None
    updated_at: str | None = None
    last_analysis_at: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip().lower().replace(" ", "-")
        if not re.match(r"^[a-z0-9][a-z0-9_-]*$", v):
            raise ValueError(
                "Project name must start with alphanumeric and contain only "
                "letters, digits, hyphens, and underscores"
            )
        return v
