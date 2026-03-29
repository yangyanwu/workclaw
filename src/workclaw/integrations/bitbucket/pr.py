"""Bitbucket Pull Request management for WorkClaw."""

from __future__ import annotations

import logging
from typing import Any, Optional

from workclaw.integrations.bitbucket.client import BitbucketClient

logger = logging.getLogger(__name__)


class BitbucketPRManager:
    """Manages pull request lifecycle on Bitbucket."""

    def __init__(self, client: BitbucketClient) -> None:
        self.client = client

    async def create_pr(
        self,
        workspace: str,
        repo_slug: str,
        title: str,
        description: str,
        source_branch: str,
        destination_branch: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a pull request."""
        if destination_branch is None:
            destination_branch = await self.client.get_default_branch(
                workspace, repo_slug
            )

        data = {
            "title": title,
            "description": description,
            "source": {"branch": {"name": source_branch}},
            "destination": {"branch": {"name": destination_branch}},
            "close_source_branch": True,
        }

        result = await self.client._request(
            "POST",
            f"/repositories/{workspace}/{repo_slug}/pullrequests",
            json=data,
        )

        pr_id = result.get("id")
        pr_url = result.get("links", {}).get("html", {}).get("href", "")
        logger.info(f"Created Bitbucket PR #{pr_id}: {pr_url}")
        return result

    async def get_pr(
        self, workspace: str, repo_slug: str, pr_id: int
    ) -> dict[str, Any]:
        """Get details of a pull request."""
        return await self.client._request(
            "GET",
            f"/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}",
        )

    async def list_prs(
        self,
        workspace: str,
        repo_slug: str,
        state: str = "OPEN",
    ) -> list[dict[str, Any]]:
        """List pull requests."""
        result = await self.client._request(
            "GET",
            f"/repositories/{workspace}/{repo_slug}/pullrequests",
            params={"state": state},
        )
        return result.get("values", [])

    async def add_comment(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: int,
        body: str,
    ) -> dict[str, Any]:
        """Add a comment to a pull request."""
        return await self.client._request(
            "POST",
            f"/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments",
            json={"content": {"raw": body}},
        )

    async def update_pr(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update a pull request."""
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if description:
            data["description"] = description

        return await self.client._request(
            "PUT",
            f"/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}",
            json=data,
        )
