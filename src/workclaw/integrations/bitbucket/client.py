"""Bitbucket REST API client for WorkClaw."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from workclaw.integrations.base import Integration

logger = logging.getLogger(__name__)

BITBUCKET_API_BASE = "https://api.bitbucket.org/2.0"


class BitbucketClient(Integration):
    """Client for Bitbucket REST API v2.0.

    Authentication via App Password (username + app_password as Basic Auth).
    """

    name = "bitbucket"

    def __init__(self, username: str, app_password: str) -> None:
        self.username = username
        self.app_password = app_password
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> bool:
        """Initialize the HTTP client and verify authentication."""
        self._client = httpx.AsyncClient(
            base_url=BITBUCKET_API_BASE,
            auth=(self.username, self.app_password),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )
        return await self.health_check()

    async def health_check(self) -> bool:
        """Verify authentication by fetching the current user."""
        try:
            resp = await self._request("GET", "/user")
            logger.info(f"Bitbucket authenticated as: {resp.get('display_name', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Bitbucket health check failed: {e}")
            return False

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # --- Repository Operations ---

    async def list_repos(
        self, workspace: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """List repositories in a workspace."""
        ws = workspace or self.username
        result = await self._request("GET", f"/repositories/{ws}")
        return result.get("values", [])

    async def get_repo(self, workspace: str, repo_slug: str) -> dict[str, Any]:
        """Get repository metadata."""
        return await self._request("GET", f"/repositories/{workspace}/{repo_slug}")

    async def get_file_content(
        self,
        workspace: str,
        repo_slug: str,
        path: str,
        ref: Optional[str] = None,
    ) -> str:
        """Get the content of a single file as text."""
        commit = ref or "HEAD"
        if not self._client:
            raise RuntimeError("Bitbucket client not connected.")

        resp = await self._client.get(
            f"/repositories/{workspace}/{repo_slug}/src/{commit}/{path}"
        )
        resp.raise_for_status()
        return resp.text

    async def get_tree(
        self,
        workspace: str,
        repo_slug: str,
        ref: str = "HEAD",
        path: str = "",
    ) -> list[dict[str, Any]]:
        """Get directory listing for a path in the repo."""
        result = await self._request(
            "GET",
            f"/repositories/{workspace}/{repo_slug}/src/{ref}/{path}",
        )
        return result.get("values", [])

    async def get_default_branch(self, workspace: str, repo_slug: str) -> str:
        """Get the default branch (main branch) of a repository."""
        result = await self._request(
            "GET", f"/repositories/{workspace}/{repo_slug}/branching-model"
        )
        development = result.get("development", {})
        branch = development.get("branch", {})
        return branch.get("name", "main")

    # --- Branch Operations ---

    async def create_branch(
        self,
        workspace: str,
        repo_slug: str,
        branch_name: str,
        from_ref: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new branch."""
        target = {}
        if from_ref:
            target = {"target": {"hash": from_ref}}

        return await self._request(
            "POST",
            f"/repositories/{workspace}/{repo_slug}/refs/branches",
            json={"name": branch_name, **target},
        )

    async def list_branches(
        self, workspace: str, repo_slug: str
    ) -> list[dict[str, Any]]:
        """List branches in a repository."""
        result = await self._request(
            "GET", f"/repositories/{workspace}/{repo_slug}/refs/branches"
        )
        return result.get("values", [])

    # --- Internal ---

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> Any:
        """Make an authenticated request to the Bitbucket API."""
        if not self._client:
            raise RuntimeError("Bitbucket client not connected. Call connect() first.")

        resp = await self._client.request(method, endpoint, params=params, json=json)

        if resp.status_code == 404:
            raise ValueError(f"Bitbucket resource not found: {endpoint}")
        if resp.status_code == 401:
            raise PermissionError("Bitbucket authentication failed")
        if resp.status_code == 403:
            raise PermissionError("Bitbucket access denied")

        resp.raise_for_status()
        return resp.json()
