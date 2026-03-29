"""WorkClaw configuration management using Pydantic Settings."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"


class WorkClawSettings(BaseSettings):
    """Main configuration for WorkClaw.

    Settings are loaded in priority order:
    1. Environment variables (highest priority)
    2. .env file
    3. ~/.workclaw/config.yaml
    4. Defaults (lowest priority)
    """

    model_config = SettingsConfigDict(
        env_prefix="WORKCLAW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM Configuration ---
    llm_provider: LLMProvider = Field(
        default=LLMProvider.OPENAI,
        description="LLM provider to use",
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="Model name (will be prefixed with provider if needed)",
    )
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=4096, ge=1)

    # --- API Keys (loaded from env without WORKCLAW_ prefix) ---
    openai_api_key: Optional[SecretStr] = Field(default=None)
    anthropic_api_key: Optional[SecretStr] = Field(default=None)
    google_api_key: Optional[SecretStr] = Field(default=None)
    ollama_api_base: str = Field(default="http://localhost:11434")

    # --- GitHub ---
    github_token: Optional[SecretStr] = Field(default=None)
    github_default_owner: Optional[str] = Field(default=None)

    # --- Bitbucket ---
    bitbucket_username: Optional[str] = Field(default=None)
    bitbucket_app_password: Optional[SecretStr] = Field(default=None)
    bitbucket_default_workspace: Optional[str] = Field(default=None)

    # --- Jira ---
    jira_url: Optional[str] = Field(default=None)
    jira_email: Optional[str] = Field(default=None)
    jira_api_token: Optional[SecretStr] = Field(default=None)
    jira_default_project: Optional[str] = Field(default=None)

    # --- Storage ---
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".workclaw" / "data")
    workspace_dir: Path = Field(
        default_factory=lambda: Path.home() / ".workclaw" / "workspaces"
    )

    # --- Agent ---
    agent_max_iterations: int = Field(default=15, ge=1, le=50)
    agent_max_context_tokens: int = Field(default=120000)

    # --- GUI ---
    gui_host: str = Field(default="0.0.0.0")
    gui_port: int = Field(default=8000)

    def get_llm_model_string(self) -> str:
        """Get the full model string for LiteLLM (e.g., 'openai/gpt-4o')."""
        model = self.llm_model
        provider = self.llm_provider.value

        # If the model already has a provider prefix, return as-is
        if "/" in model:
            return model

        # Map provider to LiteLLM prefix
        prefix_map = {
            "openai": "openai",
            "anthropic": "anthropic",
            "google": "gemini",
            "ollama": "ollama",
        }
        prefix = prefix_map.get(provider, provider)
        return f"{prefix}/{model}"

    def get_active_api_key(self) -> Optional[str]:
        """Get the API key for the currently configured provider."""
        key_map = {
            LLMProvider.OPENAI: self.openai_api_key,
            LLMProvider.ANTHROPIC: self.anthropic_api_key,
            LLMProvider.GOOGLE: self.google_api_key,
            LLMProvider.OLLAMA: None,  # Ollama doesn't need a key
        }
        key = key_map.get(self.llm_provider)
        return key.get_secret_value() if key else None

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "conversations").mkdir(exist_ok=True)
        (self.data_dir / "memory").mkdir(exist_ok=True)
        (self.data_dir / "analysis_reports").mkdir(exist_ok=True)


def load_yaml_config(config_path: Path | None = None) -> dict:
    """Load configuration from a YAML file."""
    if config_path is None:
        config_path = Path.home() / ".workclaw" / "config.yaml"

    if not config_path.exists():
        return {}

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    return data


def get_settings(**overrides) -> WorkClawSettings:
    """Get WorkClaw settings, merging YAML config with env vars.

    Priority: overrides > env vars > .env file > YAML config > defaults
    """
    yaml_config = load_yaml_config()

    # Set YAML values as env vars (low priority, won't override existing)
    for key, value in yaml_config.items():
        env_key = f"WORKCLAW_{key.upper()}"
        if env_key not in os.environ and value is not None:
            os.environ[env_key] = str(value)

    settings = WorkClawSettings(**overrides)
    settings.ensure_directories()
    return settings
