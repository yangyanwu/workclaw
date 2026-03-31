"""Project management — define multi-repo projects for consolidated code analysis."""

from workclaw.projects.manager import ProjectManager
from workclaw.projects.models import AuthMethod, ProjectConfig, RepoSource

__all__ = ["AuthMethod", "ProjectConfig", "ProjectManager", "RepoSource"]
