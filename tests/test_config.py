"""Tests for WorkClaw configuration system."""

from pathlib import Path

from workclaw.config.settings import WorkClawSettings, LLMProvider, get_settings


def test_default_settings():
    """Test that default settings are valid."""
    settings = WorkClawSettings()
    assert settings.llm_provider == LLMProvider.OPENAI
    assert settings.llm_model == "gpt-4o"
    assert settings.llm_temperature == 0.1
    assert settings.agent_max_iterations == 15
    assert settings.gui_port == 8000


def test_model_string_openai():
    """Test model string generation for OpenAI."""
    settings = WorkClawSettings(llm_provider=LLMProvider.OPENAI, llm_model="gpt-4o")
    assert settings.get_llm_model_string() == "openai/gpt-4o"


def test_model_string_anthropic():
    """Test model string generation for Anthropic."""
    settings = WorkClawSettings(llm_provider=LLMProvider.ANTHROPIC, llm_model="claude-3.5-sonnet")
    assert settings.get_llm_model_string() == "anthropic/claude-3.5-sonnet"


def test_model_string_google():
    """Test model string generation for Google."""
    settings = WorkClawSettings(llm_provider=LLMProvider.GOOGLE, llm_model="gemini-pro")
    assert settings.get_llm_model_string() == "gemini/gemini-pro"


def test_model_string_ollama():
    """Test model string generation for Ollama."""
    settings = WorkClawSettings(llm_provider=LLMProvider.OLLAMA, llm_model="llama3")
    assert settings.get_llm_model_string() == "ollama/llama3"


def test_model_string_with_prefix():
    """Model strings that already have a prefix should not be double-prefixed."""
    settings = WorkClawSettings(llm_provider=LLMProvider.OPENAI, llm_model="openai/gpt-4o")
    assert settings.get_llm_model_string() == "openai/gpt-4o"


def test_ensure_directories(tmp_path):
    """Test that directories are created."""
    data_dir = tmp_path / "data"
    ws_dir = tmp_path / "workspaces"
    settings = WorkClawSettings(data_dir=data_dir, workspace_dir=ws_dir)
    settings.ensure_directories()

    assert data_dir.exists()
    assert ws_dir.exists()
    assert (data_dir / "conversations").exists()
    assert (data_dir / "memory").exists()
    assert (data_dir / "analysis_reports").exists()
