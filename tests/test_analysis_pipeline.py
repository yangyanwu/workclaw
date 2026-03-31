"""Tests for AnalysisPipeline — consolidated report generation and storage."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workclaw.analysis.analyzer import RepoAnalysisReport
from workclaw.analysis.pipeline import AnalysisPipeline, ProjectAnalysisResult
from workclaw.projects.models import ProjectConfig, RepoSource
from workclaw.storage.store import FileStore


@pytest.fixture
def mock_llm():
    """Mock LLM provider."""
    llm = MagicMock()
    response = MagicMock()
    response.content = "## Architecture Overview\nThe system uses microservices."
    llm.achat = AsyncMock(return_value=response)
    return llm


@pytest.fixture
def pipeline(tmp_data_dir, tmp_path, mock_llm):
    """AnalysisPipeline with mocked LLM and temp dirs."""
    store = FileStore(tmp_data_dir)
    workspace = tmp_path / "workspaces"
    return AnalysisPipeline(mock_llm, store, workspace)


@pytest.fixture
def sample_project():
    """Sample project with one repo."""
    return ProjectConfig(
        name="test-project",
        description="Test project",
        repos=[
            RepoSource(url="https://github.com/owner/repo1.git", provider="github"),
        ],
    )


def _mock_patcher(target, analyzer, new_callable=AsyncMock):
    """Helper to avoid long lines with nested patch/patch.object."""
    return (
        patch("workclaw.analysis.pipeline.clone_repo"),
        patch.object(analyzer, "analyze_repo", new_callable=new_callable),
    )


class TestAnalysisPipeline:
    """Tests for AnalysisPipeline.analyze_project."""

    @pytest.mark.asyncio
    async def test_analyze_project_with_mocked_clone(
        self, pipeline, sample_project, tmp_data_dir
    ):
        """Full pipeline test with clone and analysis mocked."""
        mock_report = RepoAnalysisReport(
            repo_path="/fake/path",
            total_files=10,
            analyzed_files=5,
            overall_summary="Test summary for repo1",
            top_issues=[{"severity": "medium", "desc": "test issue"}],
        )

        p1, p2 = _mock_patcher("clone_repo", pipeline.analyzer)
        with p1 as mock_clone, p2 as mock_analyze:
            mock_clone.return_value = MagicMock(
                success=True, path=Path("/fake/repo")
            )
            mock_analyze.return_value = mock_report

            result = await pipeline.analyze_project(sample_project)

        assert isinstance(result, ProjectAnalysisResult)
        assert result.project_name == "test-project"
        assert result.success_count == 1
        assert result.failure_count == 0
        assert result.consolidated_markdown != ""
        assert "# Project: test-project" in result.consolidated_markdown

    @pytest.mark.asyncio
    async def test_analyze_project_clone_failure(self, pipeline, sample_project):
        """Pipeline handles clone failure gracefully."""
        with patch("workclaw.analysis.pipeline.clone_repo") as mock_clone:
            mock_clone.return_value = MagicMock(
                success=False, error="Repository not found"
            )

            result = await pipeline.analyze_project(sample_project)

        assert result.success_count == 0
        assert result.failure_count == 1
        assert result.repo_results[0].error == "Repository not found"

    @pytest.mark.asyncio
    async def test_analyze_project_saves_markdown(self, pipeline, sample_project):
        """Verify consolidated MD is saved to FileStore."""
        mock_report = RepoAnalysisReport(
            repo_path="/fake", total_files=1, analyzed_files=1,
        )

        p1, p2 = _mock_patcher("clone_repo", pipeline.analyzer)
        with p1 as mock_clone, p2 as mock_analyze:
            mock_clone.return_value = MagicMock(
                success=True, path=Path("/fake")
            )
            mock_analyze.return_value = mock_report

            result = await pipeline.analyze_project(sample_project)

        assert result.output_path is not None
        assert result.output_path.exists()
        content = result.output_path.read_text()
        assert "test-project" in content

    @pytest.mark.asyncio
    async def test_analyze_project_saves_per_repo_json(
        self, pipeline, sample_project, tmp_data_dir
    ):
        """Verify per-repo JSON reports are saved."""
        store = pipeline.store
        mock_report = RepoAnalysisReport(
            repo_path="/fake", total_files=5, analyzed_files=3,
        )

        p1, p2 = _mock_patcher("clone_repo", pipeline.analyzer)
        with p1 as mock_clone, p2 as mock_analyze:
            mock_clone.return_value = MagicMock(
                success=True, path=Path("/fake")
            )
            mock_analyze.return_value = mock_report

            await pipeline.analyze_project(sample_project)

        keys = store.list_keys("project_analysis", ".json")
        assert len(keys) >= 1
        assert any("test-project" in k for k in keys)

    @pytest.mark.asyncio
    async def test_analyze_multi_repo_project(self, pipeline, tmp_data_dir):
        """Pipeline handles multiple repos."""
        project = ProjectConfig(
            name="multi",
            repos=[
                RepoSource(url="https://github.com/owner/repo1.git"),
                RepoSource(url="https://github.com/owner/repo2.git"),
            ],
        )

        mock_report = RepoAnalysisReport(
            repo_path="/fake", total_files=1, analyzed_files=1,
        )

        p1, p2 = _mock_patcher("clone_repo", pipeline.analyzer)
        with p1 as mock_clone, p2 as mock_analyze:
            mock_clone.return_value = MagicMock(
                success=True, path=Path("/fake")
            )
            mock_analyze.return_value = mock_report

            result = await pipeline.analyze_project(project)

        assert result.success_count == 2
        assert result.failure_count == 0

    @pytest.mark.asyncio
    async def test_force_reclone_removes_existing(
        self, pipeline, sample_project, tmp_path
    ):
        """Force reclone removes existing workspace directory."""
        workspace = tmp_path / "workspaces"
        project_dir = workspace / "test-project"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "old_file.txt").write_text("old")

        p1, p2 = _mock_patcher("clone_repo", pipeline.analyzer)
        with p1 as mock_clone, p2:
            mock_clone.return_value = MagicMock(success=False, error="test")

            await pipeline.analyze_project(sample_project, force_reclone=True)

        assert not (project_dir / "old_file.txt").exists()

    @pytest.mark.asyncio
    async def test_consolidated_report_contains_metadata(
        self, pipeline, sample_project
    ):
        """Report includes generated timestamp and repo counts."""
        mock_report = RepoAnalysisReport(
            repo_path="/fake", total_files=1, analyzed_files=1,
        )

        p1, p2 = _mock_patcher("clone_repo", pipeline.analyzer)
        with p1 as mock_clone, p2 as mock_analyze:
            mock_clone.return_value = MagicMock(
                success=True, path=Path("/fake")
            )
            mock_analyze.return_value = mock_report

            result = await pipeline.analyze_project(sample_project)

        md = result.consolidated_markdown
        assert "Generated:" in md
        assert "1 ok" in md
        assert "0 failed" in md
