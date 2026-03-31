"""Tests for git_clone — clone command construction per auth method (mocked subprocess)."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workclaw.projects.git_clone import (
    build_clone_command,
    clone_repo,
)
from workclaw.projects.models import AuthMethod, RepoSource


class TestBuildCloneCommand:
    """Tests for build_clone_command — verifies command and env construction."""

    def test_public_https(self):
        source = RepoSource(url="https://github.com/owner/repo.git")
        args, env = build_clone_command(source, Path("/tmp/dest"))
        assert args == [
            "git", "clone", "--depth", "1",
            "https://github.com/owner/repo.git", "/tmp/dest",
        ]
        assert env == {}

    def test_https_with_branch(self):
        source = RepoSource(
            url="https://github.com/owner/repo.git", branch="develop"
        )
        args, env = build_clone_command(source, Path("/tmp/dest"))
        assert "--branch" in args
        assert "develop" in args

    def test_ssh_agent(self):
        source = RepoSource(
            url="git@github.com:owner/repo.git",
            auth_method=AuthMethod.SSH_AGENT,
        )
        args, env = build_clone_command(source, Path("/tmp/dest"))
        assert args[-2] == "git@github.com:owner/repo.git"
        assert "GIT_SSH_COMMAND" in env
        assert "StrictHostKeyChecking=accept-new" in env["GIT_SSH_COMMAND"]
        assert "IdentitiesOnly=yes" not in env["GIT_SSH_COMMAND"]

    def test_ssh_key_with_explicit_path(self):
        source = RepoSource(
            url="git@github.com:owner/repo.git",
            auth_method=AuthMethod.SSH_KEY,
            ssh_key_path=Path("/home/user/.ssh/custom_key"),
        )
        args, env = build_clone_command(source, Path("/tmp/dest"))
        assert "GIT_SSH_COMMAND" in env
        assert "-i /home/user/.ssh/custom_key" in env["GIT_SSH_COMMAND"]
        assert "IdentitiesOnly=yes" in env["GIT_SSH_COMMAND"]

    def test_https_credentials_builds_url(self):
        source = RepoSource(
            url="https://bitbucket.org/owner/repo.git",
            auth_method=AuthMethod.HTTPS_CREDENTIALS,
            username="myuser",
            password_env_var="BB_PASS",
        )
        with patch.dict(os.environ, {"BB_PASS": "secret123"}):
            args, env = build_clone_command(source, Path("/tmp/dest"))
        # URL should contain credentials
        assert "myuser:secret123@bitbucket.org" in args[-2]
        assert env == {}

    def test_https_credentials_missing_env_var(self):
        source = RepoSource(
            url="https://bitbucket.org/owner/repo.git",
            auth_method=AuthMethod.HTTPS_CREDENTIALS,
            username="myuser",
            password_env_var="MISSING_VAR_XYZ",
        )
        with pytest.raises(ValueError, match="not set or empty"):
            build_clone_command(source, Path("/tmp/dest"))


class TestCloneRepo:
    """Tests for clone_repo — mocked subprocess execution."""

    @pytest.mark.asyncio
    async def test_successful_clone(self, tmp_path):
        source = RepoSource(url="https://github.com/owner/repo.git")
        dest = tmp_path / "repo"

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "workclaw.projects.git_clone.asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            result = await clone_repo(source, dest)

        assert result.success is True
        assert result.path == dest

    @pytest.mark.asyncio
    async def test_clone_failure(self, tmp_path):
        source = RepoSource(url="https://github.com/owner/repo.git")
        dest = tmp_path / "repo"

        mock_proc = MagicMock()
        mock_proc.returncode = 128
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"fatal: repository not found")
        )

        with patch(
            "workclaw.projects.git_clone.asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            result = await clone_repo(source, dest)

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_clone_timeout(self, tmp_path):
        source = RepoSource(url="https://github.com/owner/repo.git")
        dest = tmp_path / "repo"

        with patch(
            "workclaw.projects.git_clone.asyncio.create_subprocess_exec",
            side_effect=TimeoutError,
        ):
            # asyncio.wait_for raises asyncio.TimeoutError
            with patch(
                "workclaw.projects.git_clone.asyncio.wait_for",
                side_effect=TimeoutError,
            ):
                result = await clone_repo(source, dest, timeout=5)

        assert result.success is False
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_clone_existing_dir_skips(self, tmp_path):
        source = RepoSource(url="https://github.com/owner/repo.git")
        dest = tmp_path / "repo"
        dest.mkdir()  # pre-create

        result = await clone_repo(source, dest)
        assert result.success is True
        assert result.path == dest

    @pytest.mark.asyncio
    async def test_clone_bad_auth_returns_error(self, tmp_path):
        source = RepoSource(
            url="https://bitbucket.org/owner/repo.git",
            auth_method=AuthMethod.HTTPS_CREDENTIALS,
            password_env_var="NONEXISTENT_VAR",
        )
        dest = tmp_path / "repo"

        result = await clone_repo(source, dest)
        assert result.success is False
        assert "not set" in result.error
