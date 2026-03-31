"""ProjectManager — CRUD operations for project configurations via FileStore."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from workclaw.projects.models import ProjectConfig, RepoSource
from workclaw.storage.store import FileStore

logger = logging.getLogger(__name__)

COLLECTION = "projects"


class ProjectManager:
    """Manages project configuration files on disk."""

    def __init__(self, store: FileStore) -> None:
        self.store = store

    def create_project(self, config: ProjectConfig) -> ProjectConfig:
        """Create a new project. Raises ValueError if name already exists."""
        if self.get_project(config.name):
            raise ValueError(f"Project '{config.name}' already exists")

        now = datetime.now(UTC).isoformat()
        config.created_at = now
        config.updated_at = now
        self._save(config)
        logger.info(f"Created project: {config.name}")
        return config

    def get_project(self, name: str) -> ProjectConfig | None:
        """Load a project by name. Returns None if not found."""
        data = self.store.load_yaml(COLLECTION, name)
        if data is None:
            return None
        # Remove internal metadata added by FileStore
        data.pop("_updated_at", None)
        return ProjectConfig(**data)

    def list_projects(self) -> list[ProjectConfig]:
        """List all saved projects."""
        keys = self.store.list_keys(COLLECTION, suffix=".yaml")
        projects = []
        for key in keys:
            project = self.get_project(key)
            if project:
                projects.append(project)
        return projects

    def update_project(self, name: str, updates: dict) -> ProjectConfig:
        """Update fields on an existing project."""
        project = self.get_project(name)
        if not project:
            raise ValueError(f"Project '{name}' not found")

        for key, value in updates.items():
            if hasattr(project, key):
                setattr(project, key, value)

        project.updated_at = datetime.now(UTC).isoformat()
        self._save(project)
        logger.info(f"Updated project: {name}")
        return project

    def delete_project(self, name: str) -> bool:
        """Delete a project. Returns True if deleted, False if not found."""
        project = self.get_project(name)
        if not project:
            return False
        result = self.store.delete(COLLECTION, name)
        if result:
            logger.info(f"Deleted project: {name}")
        return result

    def add_repo(self, project_name: str, repo: RepoSource) -> ProjectConfig:
        """Add a repository to a project."""
        project = self.get_project(project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")

        # Check for duplicate URL
        if any(r.url == repo.url for r in project.repos):
            raise ValueError(f"Repository '{repo.url}' already in project")

        project.repos.append(repo)
        project.updated_at = datetime.now(UTC).isoformat()
        self._save(project)
        logger.info(f"Added repo {repo.url} to project {project_name}")
        return project

    def remove_repo(self, project_name: str, repo_url: str) -> ProjectConfig:
        """Remove a repository from a project by URL."""
        project = self.get_project(project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")

        original_len = len(project.repos)
        project.repos = [r for r in project.repos if r.url != repo_url]

        if len(project.repos) == original_len:
            raise ValueError(f"Repository '{repo_url}' not found in project")

        project.updated_at = datetime.now(UTC).isoformat()
        self._save(project)
        logger.info(f"Removed repo {repo_url} from project {project_name}")
        return project

    def validate_project(self, config: ProjectConfig) -> list[str]:
        """Validate a project config, returning a list of warning messages."""
        warnings: list[str] = []

        for repo in config.repos:
            if repo.auth_method == "ssh_key" and not repo.ssh_key_path:
                warnings.append(
                    f"Repo {repo.name}: SSH key auth selected but no ssh_key_path set"
                )
            if repo.auth_method == "https_credentials":
                if not repo.username:
                    warnings.append(f"Repo {repo.name}: HTTPS credentials auth requires username")
                if not repo.password_env_var:
                    warnings.append(
                        f"Repo {repo.name}: HTTPS credentials auth requires password_env_var"
                    )

        if config.schedule_cron:
            parts = config.schedule_cron.split()
            if len(parts) != 5:
                warnings.append(
                    f"Invalid cron expression: '{config.schedule_cron}' (expected 5 fields)"
                )

        return warnings

    def _save(self, config: ProjectConfig) -> None:
        self.store.save_yaml(COLLECTION, config.name, config.model_dump(mode="json"))
