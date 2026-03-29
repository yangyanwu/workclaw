"""GitHub Pull Request management for WorkClaw."""

from __future__ import annotations

import logging
from typing import Any, Optional

from workclaw.integrations.github.client import GitHubClient

logger = logging.getLogger(__name__)


class GitHubPRManager:
    """Manages pull request lifecycle on GitHub."""

    def __init__(self, client: GitHubClient) -> None:
        self.client = client

    async def create_pr(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: Optional[str] = None,
        draft: bool = False,
    ) -> dict[str, Any]:
        """Create a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            title: PR title
            body: PR description (Markdown)
            head: Source branch name
            base: Target branch name (defaults to repo's default branch)
            draft: Whether to create as draft PR

        Returns:
            PR data including 'html_url', 'number', 'state'
        """
        if base is None:
            base = await self.client.get_default_branch(owner, repo)

        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": draft,
        }

        result = await self.client._request(
            "POST", f"/repos/{owner}/{repo}/pulls", json=data
        )

        logger.info(
            f"Created PR #{result['number']}: {result['html_url']}"
        )
        return result

    async def get_pr(
        self, owner: str, repo: str, pr_number: int
    ) -> dict[str, Any]:
        """Get details of a pull request."""
        return await self.client._request(
            "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}"
        )

    async def list_prs(
        self,
        owner: str,
        repo: str,
        state: str = "open",
    ) -> list[dict[str, Any]]:
        """List pull requests for a repository."""
        return await self.client._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": 50},
        )

    async def add_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
    ) -> dict[str, Any]:
        """Add a comment to a pull request."""
        return await self.client._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )

    async def add_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        path: str,
        line: int,
        commit_id: str,
    ) -> dict[str, Any]:
        """Add an inline review comment to a specific file/line in a PR."""
        return await self.client._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            json={
                "body": body,
                "path": path,
                "line": line,
                "commit_id": commit_id,
            },
        )

    async def update_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update a pull request's title, body, or state."""
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if body:
            data["body"] = body
        if state:
            data["state"] = state

        return await self.client._request(
            "PATCH", f"/repos/{owner}/{repo}/pulls/{pr_number}", json=data
        )

    async def get_pr_files(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        """List files changed in a pull request."""
        return await self.client._request(
            "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/files"
        )
