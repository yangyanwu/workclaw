"""LLM provider abstraction layer using LiteLLM for unified multi-provider support."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

import litellm
from litellm import acompletion, completion

from workclaw.config.settings import WorkClawSettings

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose logging
litellm.suppress_debug_info = True


@dataclass
class LLMResponse:
    """Structured response from an LLM call."""

    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    finish_reason: str = ""


class LLMProvider:
    """Unified interface for LLM providers via LiteLLM.

    Supports: OpenAI, Anthropic, Google Gemini, Ollama (local).
    """

    def __init__(self, settings: WorkClawSettings) -> None:
        self.settings = settings
        self.model = settings.get_llm_model_string()
        self._configure_provider()

    def _configure_provider(self) -> None:
        """Set up API keys and base URLs for the active provider."""
        api_key = self.settings.get_active_api_key()
        if api_key:
            # LiteLLM reads from environment, but we can also pass directly
            import os

            provider = self.settings.llm_provider.value
            key_env_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "google": "GEMINI_API_KEY",
            }
            env_var = key_env_map.get(provider)
            if env_var:
                os.environ[env_var] = api_key

        if self.settings.llm_provider.value == "ollama":
            import os

            os.environ["OLLAMA_API_BASE"] = self.settings.ollama_api_base

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Synchronous chat completion."""
        kwargs = self._build_kwargs(messages, tools, temperature, max_tokens)

        try:
            response = completion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    async def achat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Async chat completion."""
        kwargs = self._build_kwargs(messages, tools, temperature, max_tokens)

        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"LLM async call failed: {e}")
            raise

    async def astream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Async streaming chat completion — yields content chunks."""
        kwargs = self._build_kwargs(messages, tools, temperature, max_tokens)
        kwargs["stream"] = True

        try:
            response = await acompletion(**kwargs)
            async for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.error(f"LLM stream failed: {e}")
            raise

    def _build_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Build kwargs for LiteLLM completion call."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.settings.llm_temperature,
            "max_tokens": max_tokens or self.settings.llm_max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        return kwargs

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse a LiteLLM response into our structured format."""
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    }
                )

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            usage=usage,
            model=response.model or self.model,
            finish_reason=choice.finish_reason or "",
        )

    def switch_model(self, provider: str, model: str) -> None:
        """Switch to a different LLM provider/model at runtime."""
        from workclaw.config.settings import LLMProvider as ProviderEnum

        self.settings.llm_provider = ProviderEnum(provider)
        self.settings.llm_model = model
        self.model = self.settings.get_llm_model_string()
        self._configure_provider()
        logger.info(f"Switched to model: {self.model}")
