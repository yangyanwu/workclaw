"""AnalysisPipeline — clone all repos, analyze each, generate consolidated markdown."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from workclaw.analysis.analyzer import CodeAnalyzer, RepoAnalysisReport
from workclaw.llm.prompts import PROJECT_CONSOLIDATION_PROMPT
from workclaw.llm.provider import LLMProvider
from workclaw.projects.git_clone import clone_repo
from workclaw.projects.models import ProjectConfig
from workclaw.storage.store import FileStore

logger = logging.getLogger(__name__)


@dataclass
class RepoAnalysisOutput:
    """Result of analyzing a single repository within a project."""

    repo_url: str
    repo_name: str
    clone_path: Path
    report: RepoAnalysisReport | None = None
    success: bool = False
    error: str | None = None


@dataclass
class ProjectAnalysisResult:
    """Result of analyzing an entire project."""

    project_name: str
    started_at: str = ""
    completed_at: str = ""
    repo_results: list[RepoAnalysisOutput] = field(default_factory=list)
    consolidated_markdown: str = ""
    output_path: Path | None = None
    success_count: int = 0
    failure_count: int = 0


class AnalysisPipeline:
    """Orchestrates cloning and analyzing all repos in a project."""

    def __init__(
        self,
        llm: LLMProvider,
        store: FileStore,
        workspace_dir: Path,
    ) -> None:
        self.analyzer = CodeAnalyzer(llm)
        self.llm = llm
        self.store = store
        self.workspace_dir = workspace_dir

    async def analyze_project(
        self,
        project: ProjectConfig,
        force_reclone: bool = False,
    ) -> ProjectAnalysisResult:
        """Clone and analyze all repos in a project, then generate a consolidated report."""
        started = datetime.now(UTC)
        result = ProjectAnalysisResult(
            project_name=project.name,
            started_at=started.isoformat(),
        )

        # Create project workspace
        project_dir = self.workspace_dir / project.name
        if project_dir.exists() and force_reclone:
            shutil.rmtree(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)

        # Analyze each repo
        for repo_source in project.repos:
            repo_dir = project_dir / (repo_source.name or "repo")

            # Clone (remove existing if force_reclone)
            if force_reclone and repo_dir.exists():
                shutil.rmtree(repo_dir)

            clone_result = await clone_repo(repo_source, repo_dir)
            if not clone_result.success:
                result.repo_results.append(
                    RepoAnalysisOutput(
                        repo_url=repo_source.url,
                        repo_name=repo_source.name or "unknown",
                        clone_path=repo_dir,
                        success=False,
                        error=clone_result.error,
                    )
                )
                continue

            # Analyze
            try:
                report = await self.analyzer.analyze_repo(
                    repo_path=repo_dir,
                    focus_areas=project.analysis_focus_areas,
                    max_files=project.analysis_max_files_per_repo,
                )
                result.repo_results.append(
                    RepoAnalysisOutput(
                        repo_url=repo_source.url,
                        repo_name=repo_source.name or "unknown",
                        clone_path=repo_dir,
                        report=report,
                        success=True,
                    )
                )
                # Save per-repo JSON report
                safe_name = _safe_key(repo_source.name or "unknown")
                self.store.save_json(
                    "project_analysis",
                    f"{project.name}_{safe_name}_report",
                    _report_to_dict(report),
                )
            except Exception as e:
                logger.error(f"Analysis failed for {repo_source.url}: {e}")
                result.repo_results.append(
                    RepoAnalysisOutput(
                        repo_url=repo_source.url,
                        repo_name=repo_source.name or "unknown",
                        clone_path=repo_dir,
                        success=False,
                        error=str(e),
                    )
                )

        # Summarize results
        result.success_count = sum(1 for r in result.repo_results if r.success)
        result.failure_count = sum(1 for r in result.repo_results if not r.success)

        # Generate consolidated report
        result.consolidated_markdown = await self._generate_consolidated_report(
            project, result.repo_results
        )

        # Save consolidated MD
        output_path = self.store.save_markdown(
            "project_analysis",
            f"{project.name}_analysis",
            result.consolidated_markdown,
        )
        result.output_path = output_path

        # Update timestamps
        completed = datetime.now(UTC)
        result.completed_at = completed.isoformat()

        # Update project last_analysis_at via manager
        try:
            from workclaw.projects.manager import ProjectManager

            manager = ProjectManager(self.store)
            manager.update_project(project.name, {"last_analysis_at": completed.isoformat()})
        except ValueError:
            # Project not persisted — skip update
            logger.debug(f"Project {project.name} not in store, skipping last_analysis_at update")

        logger.info(
            f"Project analysis complete: {project.name} "
            f"({result.success_count} ok, {result.failure_count} failed)"
        )
        return result

    async def _generate_consolidated_report(
        self,
        project: ProjectConfig,
        repo_results: list[RepoAnalysisOutput],
    ) -> str:
        """Generate a consolidated markdown report using LLM summarization."""
        # Build per-repo summaries
        repo_summaries = []
        for r in repo_results:
            if r.success and r.report:
                summary = (
                    f"### {r.repo_name}\n"
                    f"- URL: {r.repo_url}\n"
                    f"- Files analyzed: {r.report.analyzed_files}/{r.report.total_files}\n"
                )
                if r.report.overall_summary:
                    summary += f"\n{r.report.overall_summary}\n"
                if r.report.top_issues:
                    summary += "\n**Top Issues:**\n"
                    for issue in r.report.top_issues[:5]:
                        summary += f"- {issue}\n"
                repo_summaries.append(summary)
            else:
                repo_summaries.append(
                    f"### {r.repo_name}\n- URL: {r.repo_url}\n- Status: FAILED"
                    + (f" ({r.error})" if r.error else "")
                )

        # LLM consolidation
        prompt = PROJECT_CONSOLIDATION_PROMPT.format(
            project_name=project.name,
            project_description=project.description or "No description",
            repo_summaries="\n\n".join(repo_summaries),
        )

        try:
            response = await self.llm.achat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4096,
            )
            llm_overview = response.content
        except Exception as e:
            logger.error(f"Consolidation LLM call failed: {e}")
            llm_overview = "*(Consolidation LLM call failed — showing raw summaries)*"

        # Assemble full markdown
        ok = sum(1 for r in repo_results if r.success)
        fail = sum(1 for r in repo_results if not r.success)
        ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            f"# Project: {project.name}",
            f"> Generated: {ts} | Repos: {len(repo_results)} | Status: {ok} ok, {fail} failed",
            "",
        ]
        if project.description:
            lines.append(f"**Description**: {project.description}")
            lines.append("")

        lines.append("## Architecture Overview")
        lines.append("")
        lines.append(llm_overview)
        lines.append("")

        lines.append("## Repository Summaries")
        lines.append("")
        for r in repo_results:
            if r.success and r.report:
                lines.append(f"### {r.repo_name}")
                lines.append(f"- **URL**: `{r.repo_url}`")
                files = f"{r.report.analyzed_files}/{r.report.total_files}"
                lines.append(f"- **Files analyzed**: {files}")
                lines.append("")
                if r.report.overall_summary:
                    lines.append(r.report.overall_summary)
                lines.append("")
            else:
                lines.append(f"### {r.repo_name}")
                lines.append(f"- **URL**: `{r.repo_url}`")
                lines.append("- **Status**: FAILED" + (f" ({r.error})" if r.error else ""))
                lines.append("")

        return "\n".join(lines)


def _safe_key(name: str) -> str:
    """Convert a repo name to a safe filesystem key."""
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _report_to_dict(report: RepoAnalysisReport) -> dict:
    """Convert a RepoAnalysisReport to a JSON-serializable dict."""
    return {
        "repo_path": report.repo_path,
        "total_files": report.total_files,
        "analyzed_files": report.analyzed_files,
        "overall_summary": report.overall_summary,
        "top_issues": report.top_issues,
        "refactoring_opportunities": report.refactoring_opportunities,
        "file_results": [
            {
                "file_path": r.file_path,
                "language": r.language,
                "summary": r.summary,
                "quality_score": r.quality_score,
            }
            for r in report.file_results
        ],
    }
