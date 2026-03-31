"""AnalysisScheduler — APScheduler-based periodic project re-analysis."""

from __future__ import annotations

import logging

from workclaw.analysis.pipeline import AnalysisPipeline
from workclaw.projects.manager import ProjectManager

logger = logging.getLogger(__name__)


class AnalysisScheduler:
    """Schedules periodic project analysis using APScheduler."""

    def __init__(
        self,
        pipeline: AnalysisPipeline,
        project_manager: ProjectManager,
    ) -> None:
        self.pipeline = pipeline
        self.project_manager = project_manager
        self._scheduler: object | None = None

    def _get_scheduler(self) -> object:
        """Lazy-import and create the AsyncIOScheduler."""
        if self._scheduler is None:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler

            self._scheduler = AsyncIOScheduler()
        return self._scheduler

    def start(self) -> None:
        """Load all projects with schedule_cron and start the scheduler."""
        sched = self._get_scheduler()

        # Register jobs for all projects that have a schedule
        projects = self.project_manager.list_projects()
        for project in projects:
            if project.schedule_cron:
                self._add_job(sched, project.name, project.schedule_cron)

        sched.start()
        logger.info("Analysis scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            logger.info("Analysis scheduler stopped")

    def add_job(self, project_name: str, cron_expression: str) -> None:
        """Add a scheduled analysis job for a project."""
        sched = self._get_scheduler()
        self._add_job(sched, project_name, cron_expression)
        # Persist the schedule to project config
        self.project_manager.update_project(
            project_name, {"schedule_cron": cron_expression}
        )
        logger.info(f"Scheduled analysis for {project_name}: {cron_expression}")

    def remove_job(self, project_name: str) -> None:
        """Remove a scheduled analysis job."""
        sched = self._get_scheduler()
        try:
            sched.remove_job(project_name)
            logger.info(f"Removed schedule for {project_name}")
        except Exception:
            logger.warning(f"No schedule found for {project_name}")
        # Clear schedule from project config
        self.project_manager.update_project(
            project_name, {"schedule_cron": None}
        )

    def list_jobs(self) -> list[dict[str, str]]:
        """List all scheduled analysis jobs."""
        sched = self._get_scheduler()
        jobs = []
        for job in sched.get_jobs():
            jobs.append(
                {
                    "project": job.id,
                    "next_run": str(job.next_run_time) if job.next_run_time else "N/A",
                    "trigger": str(job.trigger),
                }
            )
        return jobs

    def _add_job(self, sched: object, project_name: str, cron_expression: str) -> None:
        """Register a cron job on the scheduler."""
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression (expected 5 fields): {cron_expression}")

        sched.add_job(
            self._run_analysis,
            "cron",
            id=project_name,
            replace_existing=True,
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            args=[project_name],
        )

    async def _run_analysis(self, project_name: str) -> None:
        """Called by APScheduler — runs a full project analysis."""
        logger.info(f"Running scheduled analysis for: {project_name}")
        project = self.project_manager.get_project(project_name)
        if not project:
            logger.error(f"Project not found for scheduled analysis: {project_name}")
            return

        try:
            result = await self.pipeline.analyze_project(project, force_reclone=True)
            logger.info(
                f"Scheduled analysis complete for {project_name}: "
                f"{result.success_count} ok, {result.failure_count} failed"
            )
        except Exception as e:
            logger.error(f"Scheduled analysis failed for {project_name}: {e}")
