"""GitHub REST API client for WorkClaw."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import httpx

from workclaw.integrations.base import Integration

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient(Integration):
    """Client for GitHub REST API v3.

    Provides methods to read repositories, list files, and interact with
    GitHub resources. Authentication via Personal Access Token (PAT).
    """

    name = "github"

    def __init__(self, token: str) -> None:
        self.token = token
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> bool:
        """Initialize the HTTP client and verify authentication."""
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )
        return await self.health_check()

    async def health_check(self) -> bool:
        """Verify the token is valid by fetching authenticated user."""
        try:
            resp = await self._request("GET", "/user")
            logger.info(f"GitHub authenticated as: {resp.get('login', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"GitHub health check failed: {e}")
            return False

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # --- Repository Operations ---

    async def list_repos(
        self, owner: Optional[str] = None, org: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """List repositories for a user or organization."""
        if org:
            endpoint = f"/orgs/{org}/repos"
        elif owner:
            endpoint = f"/users/{owner}/repos"
        else:
            endpoint = "/user/repos"

        return await self._request("GET", endpoint, params={"per_page": 100})

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository metadata."""
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get the content of a single file.

        Returns dict with 'content' (base64), 'encoding', 'size', 'name', etc.
        """
        params = {}
        if ref:
            params["ref"] = ref
        return await self._request(
            "GET", f"/repos/{owner}/{repo}/contents/{path}", params=params
        )

    async def get_tree(
        self,
        owner: str,
        repo: str,
        ref: str = "HEAD",
        recursive: bool = True,
    ) -> list[dict[str, Any]]:
        """Get the full file tree of a repository."""
        params = {"recursive": "1"} if recursive else {}
        # First get the ref's commit to find tree SHA
        commit = await self._request(
            "GET", f"/repos/{owner}/{repo}/git/ref/heads/{ref}"
        )
        tree_sha = commit["object"]["sha"]
        result = await self._request(
            "GET", f"/repos/{owner}/{repo}/git/trees/{tree_sha}", params=params
        )
        return result.get("tree", [])

    async def get_default_branch(self, owner: str, repo: str) -> str:
        """Get the default branch name for a repository."""
        repo_data = await self.get_repo(owner, repo)
        return repo_data.get("default_branch", "main")

    # --- Branch Operations ---

    async def create_branch(
        self, owner: str, repo: str, branch_name: str, from_ref: str = "HEAD"
    ) -> dict[str, Any]:
        """Create a new branch from a reference."""
        # Get the SHA of the source ref
        default_branch = await self.get_default_branch(owner, repo)
        ref_data = await self._request(
            "GET", f"/repos/{owner}/{repo}/git/ref/heads/{default_branch}"
        )
        sha = ref_data["object"]["sha"]

        return await self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        )

    async def list_branches(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """List branches in a repository."""
        return await self._request(
            "GET", f"/repos/{owner}/{repo}/branches", params={"per_page": 100}
        )

    # --- Internal ---

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> Any:
        """Make an authenticated request to the GitHub API."""
        if not self._client:
            raise RuntimeError("GitHub client not connected. Call connect() first.")

        resp = await self._client.request(method, endpoint, params=params, json=json)

        if resp.status_code == 404:
            raise ValueError(f"GitHub resource not found: {endpoint}")
        if resp.status_code == 401:
            raise PermissionError("GitHub authentication failed — check your token")
        if resp.status_code == 403:
            raise PermissionError(
                f"GitHub access denied: {resp.json().get('message', 'Forbidden')}"
            )

        resp.raise_for_status()
        return resp.json()
