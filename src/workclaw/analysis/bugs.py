"""Bug detection — uses LLM to find potential bugs and security issues."""

from __future__ import annotations

from pathlib import Path

from workclaw.llm.prompts import BUG_DETECT_PROMPT
from workclaw.llm.provider import LLMProvider
from workclaw.analysis.analyzer import EXTENSION_MAP


class BugDetector:
    """Detects potential bugs and security issues using LLM analysis."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def analyze(self, file_path: Path) -> str:
        """Analyze a file for bugs and security issues.

        Returns a Markdown-formatted report with severity ratings
        and suggested fixes.
        """
        path = Path(file_path)
        language = EXTENSION_MAP.get(path.suffix, "text")

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Could not read file: {e}"

        if len(content) > 50000:
            return "File too large for bug detection (>50KB)."

        prompt = BUG_DETECT_PROMPT.format(
            file_path=str(path),
            language=language,
            code_content=content,
        )

        response = await self.llm.achat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        return response.content
