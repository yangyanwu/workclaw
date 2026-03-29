"""Refactoring opportunity detection — uses LLM to suggest improvements."""

from __future__ import annotations

from pathlib import Path

from workclaw.llm.prompts import REFACTOR_PROMPT
from workclaw.llm.provider import LLMProvider
from workclaw.analysis.analyzer import EXTENSION_MAP


class RefactorDetector:
    """Detects refactoring opportunities in code using LLM analysis."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def analyze(self, file_path: Path) -> str:
        """Analyze a file for refactoring opportunities.

        Returns a Markdown-formatted report with specific suggestions,
        including before/after code examples.
        """
        path = Path(file_path)
        language = EXTENSION_MAP.get(path.suffix, "text")

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Could not read file: {e}"

        if len(content) > 50000:
            return "File too large for refactoring analysis (>50KB)."

        prompt = REFACTOR_PROMPT.format(
            file_path=str(path),
            language=language,
            code_content=content,
        )

        response = await self.llm.achat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        return response.content
