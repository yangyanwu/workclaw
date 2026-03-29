"""Git operation tools — clone, branch, commit, push, diff, status."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from workclaw.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


class GitCloneTool(Tool):
    """Clone a git repository."""

    name = "git_clone"
    description = "Clone a git repository to the local workspace. Returns the path to the cloned repo."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Repository URL (HTTPS or SSH)",
            },
            "destination": {
                "type": "string",
                "description": "Local directory to clone into",
            },
            "branch": {
                "type": "string",
                "description": "Branch to clone (default: default branch)",
            },
        },
        "required": ["url", "destination"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        url = kwargs["url"]
        destination = Path(kwargs["destination"]).expanduser().resolve()
        branch = kwargs.get("branch")

        try:
            cmd = ["git", "clone", "--depth", "1"]
            if branch:
                cmd.extend(["--branch", branch])
            cmd.extend([url, str(destination)])

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False, output="", error=f"Git clone failed: {result.stderr}"
                )

            return ToolResult(
                success=True,
                output=f"Successfully cloned {url} to {destination}",
                data={"path": str(destination)},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Clone timed out after 120s")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GitBranchTool(Tool):
    """Create or switch git branches."""

    name = "git_branch"
    description = "Create a new branch or switch to an existing one in a git repository."
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the git repository",
            },
            "branch_name": {
                "type": "string",
                "description": "Name of the branch to create/switch to",
            },
            "create": {
                "type": "boolean",
                "description": "Whether to create the branch (default: true)",
            },
        },
        "required": ["repo_path", "branch_name"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        repo_path = Path(kwargs["repo_path"]).expanduser().resolve()
        branch_name = kwargs["branch_name"]
        create = kwargs.get("create", True)

        try:
            if create:
                cmd = ["git", "checkout", "-b", branch_name]
            else:
                cmd = ["git", "checkout", branch_name]

            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(repo_path), timeout=30
            )

            if result.returncode != 0:
                return ToolResult(success=False, output="", error=result.stderr.strip())

            return ToolResult(
                success=True,
                output=f"Switched to branch '{branch_name}'"
                + (" (new)" if create else ""),
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GitCommitTool(Tool):
    """Stage changes and create a commit."""

    name = "git_commit"
    description = "Stage all changes and create a commit in the repository."
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the git repository",
            },
            "message": {
                "type": "string",
                "description": "Commit message",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific files to stage (default: all changes)",
            },
        },
        "required": ["repo_path", "message"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        repo_path = Path(kwargs["repo_path"]).expanduser().resolve()
        message = kwargs["message"]
        files = kwargs.get("files")

        try:
            # Stage files
            if files:
                for f in files:
                    subprocess.run(
                        ["git", "add", f],
                        cwd=str(repo_path),
                        capture_output=True,
                        timeout=10,
                    )
            else:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=str(repo_path),
                    capture_output=True,
                    timeout=10,
                )

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                cwd=str(repo_path),
                timeout=30,
            )

            if result.returncode != 0:
                return ToolResult(success=False, output="", error=result.stderr.strip())

            return ToolResult(success=True, output=f"Committed: {message}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GitPushTool(Tool):
    """Push commits to a remote repository."""

    name = "git_push"
    description = "Push the current branch to the remote repository."
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the git repository",
            },
            "remote": {
                "type": "string",
                "description": "Remote name (default: origin)",
            },
            "branch": {
                "type": "string",
                "description": "Branch to push (default: current branch)",
            },
            "set_upstream": {
                "type": "boolean",
                "description": "Set upstream tracking (default: true for new branches)",
            },
        },
        "required": ["repo_path"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        repo_path = Path(kwargs["repo_path"]).expanduser().resolve()
        remote = kwargs.get("remote", "origin")
        branch = kwargs.get("branch")
        set_upstream = kwargs.get("set_upstream", True)

        try:
            cmd = ["git", "push"]
            if set_upstream:
                cmd.extend(["--set-upstream"])
            cmd.append(remote)
            if branch:
                cmd.append(branch)

            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(repo_path), timeout=60
            )

            if result.returncode != 0:
                return ToolResult(success=False, output="", error=result.stderr.strip())

            return ToolResult(
                success=True,
                output=f"Pushed to {remote}" + (f"/{branch}" if branch else ""),
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GitDiffTool(Tool):
    """Show diffs in a git repository."""

    name = "git_diff"
    description = "Show the git diff for the current changes or between commits/branches."
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the git repository",
            },
            "staged": {
                "type": "boolean",
                "description": "Show staged changes only (default: false)",
            },
            "ref": {
                "type": "string",
                "description": "Compare against a specific ref (branch, commit, tag)",
            },
        },
        "required": ["repo_path"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        repo_path = Path(kwargs["repo_path"]).expanduser().resolve()
        staged = kwargs.get("staged", False)
        ref = kwargs.get("ref")

        try:
            cmd = ["git", "diff"]
            if staged:
                cmd.append("--staged")
            if ref:
                cmd.append(ref)

            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(repo_path), timeout=30
            )

            output = result.stdout.strip()
            if not output:
                return ToolResult(success=True, output="No changes detected.")

            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GitStatusTool(Tool):
    """Show the status of a git repository."""

    name = "git_status"
    description = "Show the current status of a git repository (modified, staged, untracked files)."
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the git repository",
            },
        },
        "required": ["repo_path"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        repo_path = Path(kwargs["repo_path"]).expanduser().resolve()

        try:
            result = subprocess.run(
                ["git", "status", "--short", "--branch"],
                capture_output=True,
                text=True,
                cwd=str(repo_path),
                timeout=10,
            )

            return ToolResult(success=True, output=result.stdout.strip() or "Clean working tree")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
