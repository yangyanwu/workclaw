"""Code analysis coordinator — combines LLM analysis with structural checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from workclaw.llm.prompts import ANALYZE_CODE_PROMPT, JIRA_ANALYSIS_PROMPT
from workclaw.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

# Map file extensions to language names
EXTENSION_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".md": "markdown",
}

# Files/dirs to skip during analysis
SKIP_PATTERNS = {
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    ".egg-info",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


@dataclass
class AnalysisResult:
    """Result of analyzing a single file."""

    file_path: str
    language: str
    summary: str = ""
    quality_score: int = 0
    issues: list[dict[str, str]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    raw_analysis: str = ""


@dataclass
class RepoAnalysisReport:
    """Full analysis report for a repository."""

    repo_path: str
    total_files: int = 0
    analyzed_files: int = 0
    file_results: list[AnalysisResult] = field(default_factory=list)
    overall_summary: str = ""
    top_issues: list[dict[str, str]] = field(default_factory=list)
    refactoring_opportunities: list[str] = field(default_factory=list)


class CodeAnalyzer:
    """Analyzes code files and repositories using LLM + structural analysis."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def analyze_file(
        self,
        file_path: Path,
        additional_context: str = "",
    ) -> AnalysisResult:
        """Analyze a single code file."""
        path = Path(file_path)
        language = EXTENSION_MAP.get(path.suffix, "text")

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return AnalysisResult(
                file_path=str(path),
                language=language,
                summary=f"Could not read file: {e}",
            )

        # Skip very large files
        if len(content) > 50000:
            return AnalysisResult(
                file_path=str(path),
                language=language,
                summary="File too large for analysis (>50KB). Consider breaking it into smaller modules.",
            )

        prompt = ANALYZE_CODE_PROMPT.format(
            file_path=str(path),
            language=language,
            code_content=content,
            additional_context=additional_context,
        )

        response = await self.llm.achat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        return AnalysisResult(
            file_path=str(path),
            language=language,
            raw_analysis=response.content,
            summary=response.content[:200],
        )

    async def analyze_repo(
        self,
        repo_path: Path,
        focus_areas: Optional[list[str]] = None,
        max_files: int = 20,
    ) -> RepoAnalysisReport:
        """Analyze an entire repository."""
        repo = Path(repo_path)
        report = RepoAnalysisReport(repo_path=str(repo))

        # Collect analyzable files
        files = self._collect_files(repo, focus_areas)
        report.total_files = len(files)

        # Analyze up to max_files
        for file_path in files[:max_files]:
            result = await self.analyze_file(file_path)
            report.file_results.append(result)
            report.analyzed_files += 1

        # Generate overall summary
        if report.file_results:
            report.overall_summary = self._generate_summary(report)

        return report

    async def analyze_for_story(
        self,
        repo_path: Path,
        jira_story: dict[str, Any],
    ) -> str:
        """Analyze a repo in the context of a Jira story.

        Returns an implementation plan based on the story requirements
        and current codebase.
        """
        repo = Path(repo_path)

        # Get repo structure
        files = self._collect_files(repo)
        file_list = "\n".join(
            f"  - {f.relative_to(repo)}" for f in files[:50]
        )

        prompt = JIRA_ANALYSIS_PROMPT.format(
            issue_key=jira_story.get("key", ""),
            summary=jira_story.get("summary", ""),
            description=jira_story.get("description", ""),
            acceptance_criteria=jira_story.get("acceptance_criteria", "Not specified"),
            repo_info=f"Repository: {repo}\nFiles:\n{file_list}",
        )

        response = await self.llm.achat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4096,
        )

        return response.content

    def _collect_files(
        self,
        repo_path: Path,
        focus_areas: Optional[list[str]] = None,
    ) -> list[Path]:
        """Collect analyzable source files from a repository."""
        files = []

        for path in repo_path.rglob("*"):
            # Skip excluded directories
            if any(skip in path.parts for skip in SKIP_PATTERNS):
                continue

            if not path.is_file():
                continue

            # Only analyze known source files
            if path.suffix not in EXTENSION_MAP:
                continue

            # Filter by focus areas if specified
            if focus_areas:
                rel = str(path.relative_to(repo_path))
                if not any(area in rel for area in focus_areas):
                    continue

            files.append(path)

        # Sort by path for consistent ordering
        return sorted(files)

    @staticmethod
    def _generate_summary(report: RepoAnalysisReport) -> str:
        """Generate a human-readable summary of the analysis."""
        lines = [
            f"## Repository Analysis Summary",
            f"",
            f"**Path**: {report.repo_path}",
            f"**Files found**: {report.total_files}",
            f"**Files analyzed**: {report.analyzed_files}",
            f"",
        ]

        if report.file_results:
            lines.append("### File Analyses")
            for result in report.file_results:
                lines.append(f"\n#### {result.file_path}")
                lines.append(result.raw_analysis[:500] if result.raw_analysis else result.summary)

        return "\n".join(lines)
