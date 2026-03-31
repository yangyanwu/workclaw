"""Tests for ProjectManager — CRUD operations via temp FileStore."""

import pytest

from workclaw.projects.manager import ProjectManager
from workclaw.projects.models import AuthMethod, ProjectConfig, RepoSource
from workclaw.storage.store import FileStore


@pytest.fixture
def manager(tmp_data_dir):
    """ProjectManager with a temp FileStore."""
    store = FileStore(tmp_data_dir)
    return ProjectManager(store)


@pytest.fixture
def sample_config():
    """A sample ProjectConfig for testing."""
    return ProjectConfig(
        name="test-project",
        description="A test project",
        repos=[
            RepoSource(url="https://github.com/owner/repo1.git", provider="github"),
        ],
    )


class TestCreateProject:
    def test_create_project(self, manager, sample_config):
        result = manager.create_project(sample_config)
        assert result.name == "test-project"
        assert result.created_at is not None
        assert result.updated_at is not None

    def test_create_duplicate_fails(self, manager, sample_config):
        manager.create_project(sample_config)
        with pytest.raises(ValueError, match="already exists"):
            manager.create_project(sample_config)


class TestGetProject:
    def test_get_existing(self, manager, sample_config):
        manager.create_project(sample_config)
        result = manager.get_project("test-project")
        assert result is not None
        assert result.name == "test-project"

    def test_get_nonexistent(self, manager):
        result = manager.get_project("no-such-project")
        assert result is None


class TestListProjects:
    def test_list_empty(self, manager):
        projects = manager.list_projects()
        assert projects == []

    def test_list_multiple(self, manager):
        for name in ["proj-a", "proj-b", "proj-c"]:
            config = ProjectConfig(
                name=name,
                repos=[RepoSource(url=f"https://github.com/owner/{name}.git")],
            )
            manager.create_project(config)

        projects = manager.list_projects()
        assert len(projects) == 3
        names = {p.name for p in projects}
        assert names == {"proj-a", "proj-b", "proj-c"}


class TestUpdateProject:
    def test_update_description(self, manager, sample_config):
        manager.create_project(sample_config)
        updated = manager.update_project("test-project", {"description": "Updated"})
        assert updated.description == "Updated"

    def test_update_nonexistent_fails(self, manager):
        with pytest.raises(ValueError, match="not found"):
            manager.update_project("nope", {"description": "x"})


class TestDeleteProject:
    def test_delete_existing(self, manager, sample_config):
        manager.create_project(sample_config)
        assert manager.delete_project("test-project") is True
        assert manager.get_project("test-project") is None

    def test_delete_nonexistent(self, manager):
        assert manager.delete_project("nope") is False


class TestAddRepo:
    def test_add_repo(self, manager, sample_config):
        manager.create_project(sample_config)
        new_repo = RepoSource(url="https://github.com/owner/repo2.git")
        updated = manager.add_repo("test-project", new_repo)
        assert len(updated.repos) == 2

    def test_add_duplicate_url_fails(self, manager, sample_config):
        manager.create_project(sample_config)
        dup = RepoSource(url="https://github.com/owner/repo1.git")
        with pytest.raises(ValueError, match="already in project"):
            manager.add_repo("test-project", dup)

    def test_add_to_nonexistent_fails(self, manager):
        with pytest.raises(ValueError, match="not found"):
            manager.add_repo(
                "nope", RepoSource(url="https://github.com/owner/repo.git")
            )


class TestRemoveRepo:
    def test_remove_repo(self, manager):
        config = ProjectConfig(
            name="multi-repo",
            repos=[
                RepoSource(url="https://github.com/owner/repo1.git"),
                RepoSource(url="https://github.com/owner/repo2.git"),
            ],
        )
        manager.create_project(config)
        updated = manager.remove_repo("multi-repo", "https://github.com/owner/repo1.git")
        assert len(updated.repos) == 1
        assert updated.repos[0].url == "https://github.com/owner/repo2.git"

    def test_remove_last_repo_succeeds(self, manager, sample_config):
        manager.create_project(sample_config)
        updated = manager.remove_repo("test-project", sample_config.repos[0].url)
        assert updated.repos == []

    def test_remove_nonexistent_url(self, manager, sample_config):
        manager.create_project(sample_config)
        with pytest.raises(ValueError, match="not found in project"):
            manager.remove_repo("test-project", "https://github.com/nope/nope.git")


class TestValidateProject:
    def test_valid_project_no_warnings(self, manager, sample_config):
        warnings = manager.validate_project(sample_config)
        assert warnings == []

    def test_ssh_key_without_path(self, manager):
        config = ProjectConfig(
            name="test",
            repos=[
                RepoSource(
                    url="git@github.com:owner/repo.git",
                    auth_method=AuthMethod.SSH_KEY,
                ),
            ],
        )
        warnings = manager.validate_project(config)
        assert any("SSH key" in w for w in warnings)

    def test_https_creds_missing_fields(self, manager):
        config = ProjectConfig(
            name="test",
            repos=[
                RepoSource(
                    url="https://github.com/owner/repo.git",
                    auth_method=AuthMethod.HTTPS_CREDENTIALS,
                ),
            ],
        )
        warnings = manager.validate_project(config)
        assert any("username" in w for w in warnings)
        assert any("password_env_var" in w for w in warnings)

    def test_invalid_cron(self, manager):
        config = ProjectConfig(
            name="test",
            repos=[RepoSource(url="https://github.com/owner/repo.git")],
            schedule_cron="bad cron",
        )
        warnings = manager.validate_project(config)
        assert any("Invalid cron" in w for w in warnings)
