"""Tests for project models — ProjectConfig validation, RepoSource auth resolution."""

from pathlib import Path

import pytest

from workclaw.projects.models import AuthMethod, ProjectConfig, RepoSource


class TestRepoSource:
    """Tests for RepoSource model."""

    def test_https_url_valid(self):
        repo = RepoSource(url="https://github.com/owner/repo.git")
        assert repo.url == "https://github.com/owner/repo.git"
        assert repo.auth_method == AuthMethod.HTTPS

    def test_ssh_url_auto_detects_ssh_agent(self):
        repo = RepoSource(url="git@github.com:owner/repo.git")
        assert repo.auth_method == AuthMethod.SSH_AGENT

    def test_name_derived_from_https_url(self):
        repo = RepoSource(url="https://github.com/owner/repo.git")
        assert repo.name == "owner/repo"

    def test_name_derived_from_ssh_url(self):
        repo = RepoSource(url="git@github.com:owner/repo.git")
        assert repo.name == "owner/repo"

    def test_explicit_name_overrides_derived(self):
        repo = RepoSource(url="https://github.com/owner/repo.git", name="my-repo")
        assert repo.name == "my-repo"

    def test_empty_url_rejected(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            RepoSource(url="")

    def test_invalid_url_rejected(self):
        with pytest.raises(ValueError, match="must be SSH"):
            RepoSource(url="ftp://example.com/repo")

    def test_explicit_auth_ssh_key(self):
        repo = RepoSource(
            url="git@github.com:owner/repo.git",
            auth_method=AuthMethod.SSH_KEY,
            ssh_key_path=Path("~/.ssh/custom_key"),
        )
        assert repo.auth_method == AuthMethod.SSH_KEY
        assert repo.ssh_key_path == Path("~/.ssh/custom_key")

    def test_https_credentials_fields(self):
        repo = RepoSource(
            url="https://bitbucket.org/owner/repo.git",
            auth_method=AuthMethod.HTTPS_CREDENTIALS,
            username="myuser",
            password_env_var="BB_PASSWORD",
        )
        assert repo.auth_method == AuthMethod.HTTPS_CREDENTIALS
        assert repo.username == "myuser"
        assert repo.password_env_var == "BB_PASSWORD"

    def test_branch_optional(self):
        repo = RepoSource(url="https://github.com/owner/repo.git", branch="develop")
        assert repo.branch == "develop"

    def test_provider_default(self):
        repo = RepoSource(url="https://github.com/owner/repo.git")
        assert repo.provider == "other"

    def test_provider_github(self):
        repo = RepoSource(url="https://github.com/owner/repo.git", provider="github")
        assert repo.provider == "github"


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_valid_project(self):
        config = ProjectConfig(
            name="my-project",
            repos=[RepoSource(url="https://github.com/owner/repo.git")],
        )
        assert config.name == "my-project"
        assert len(config.repos) == 1

    def test_name_normalized(self):
        config = ProjectConfig(
            name="My Project",
            repos=[RepoSource(url="https://github.com/owner/repo.git")],
        )
        assert config.name == "my-project"

    def test_invalid_name_rejected(self):
        with pytest.raises(ValueError):
            ProjectConfig(
                name="invalid name!",
                repos=[RepoSource(url="https://github.com/owner/repo.git")],
            )

    def test_empty_repos_allowed(self):
        config = ProjectConfig(name="test", repos=[])
        assert config.repos == []

    def test_defaults(self):
        config = ProjectConfig(
            name="test",
            repos=[RepoSource(url="https://github.com/owner/repo.git")],
        )
        assert config.description == ""
        assert config.analysis_max_files_per_repo == 20
        assert config.analysis_focus_areas is None
        assert config.schedule_cron is None
        assert config.created_at is None

    def test_with_schedule(self):
        config = ProjectConfig(
            name="test",
            repos=[RepoSource(url="https://github.com/owner/repo.git")],
            schedule_cron="0 2 * * 1",
        )
        assert config.schedule_cron == "0 2 * * 1"

    def test_multiple_repos(self):
        config = ProjectConfig(
            name="multi",
            repos=[
                RepoSource(url="https://github.com/owner/repo1.git"),
                RepoSource(url="https://github.com/owner/repo2.git"),
                RepoSource(url="git@github.com:owner/repo3.git"),
            ],
        )
        assert len(config.repos) == 3
        assert config.repos[2].auth_method == AuthMethod.SSH_AGENT
