"""Jira REST API client for WorkClaw."""

from __future__ import annotations

import base64
import logging
from typing import Any, Optional

import httpx

from workclaw.integrations.base import Integration

logger = logging.getLogger(__name__)


class JiraClient(Integration):
    """Client for Jira REST API v3 (Atlassian Cloud).

    Authentication via email + API token (Basic Auth).
    """

    name = "jira"

    def __init__(self, url: str, email: str, api_token: str) -> None:
        self.base_url = url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> bool:
        """Initialize the HTTP client and verify authentication."""
        # Jira Cloud uses Basic Auth with email:api_token
        credentials = base64.b64encode(
            f"{self.email}:{self.api_token}".encode()
        ).decode()

        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/rest/api/3",
            headers={
                "Authorization": f"Basic {credentials}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        return await self.health_check()

    async def health_check(self) -> bool:
        """Verify authentication by fetching current user."""
        try:
            resp = await self._request("GET", "/myself")
            logger.info(f"Jira authenticated as: {resp.get('displayName', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Jira health check failed: {e}")
            return False

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # --- Issue Operations ---

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        """Fetch a Jira issue with all fields.

        Returns a simplified dict with key fields extracted for easy consumption.
        """
        raw = await self._request(
            "GET",
            f"/issue/{issue_key}",
            params={"expand": "renderedFields"},
        )

        fields = raw.get("fields", {})
        rendered = raw.get("renderedFields", {})

        return {
            "key": raw["key"],
            "id": raw["id"],
            "summary": fields.get("summary", ""),
            "description": self._extract_text(fields.get("description")),
            "description_html": rendered.get("description", ""),
            "status": fields.get("status", {}).get("name", ""),
            "priority": fields.get("priority", {}).get("name", ""),
            "issue_type": fields.get("issuetype", {}).get("name", ""),
            "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
            "reporter": (fields.get("reporter") or {}).get("displayName", "Unknown"),
            "labels": fields.get("labels", []),
            "components": [c.get("name", "") for c in fields.get("components", [])],
            "acceptance_criteria": self._extract_acceptance_criteria(fields),
            "story_points": fields.get("story_points") or fields.get("customfield_10028"),
            "sprint": self._extract_sprint(fields),
            "created": fields.get("created", ""),
            "updated": fields.get("updated", ""),
            "comments": await self._get_comments(issue_key),
        }

    async def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Search for issues using JQL."""
        data: dict[str, Any] = {
            "jql": jql,
            "maxResults": max_results,
        }
        if fields:
            data["fields"] = fields

        result = await self._request("POST", "/search", json=data)
        return result.get("issues", [])

    async def get_sprint_issues(
        self,
        project_key: str,
        sprint_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get issues in the current sprint for a project."""
        if sprint_name:
            jql = f'project = "{project_key}" AND sprint = "{sprint_name}"'
        else:
            jql = f'project = "{project_key}" AND sprint in openSprints()'
        return await self.search_issues(jql)

    # --- Issue Mutations ---

    async def update_issue_status(
        self, issue_key: str, transition_name: str
    ) -> bool:
        """Transition an issue to a new status (e.g., 'In Progress', 'Done')."""
        # Get available transitions
        transitions = await self._request(
            "GET", f"/issue/{issue_key}/transitions"
        )

        target = None
        for t in transitions.get("transitions", []):
            if t["name"].lower() == transition_name.lower():
                target = t
                break

        if not target:
            available = [t["name"] for t in transitions.get("transitions", [])]
            logger.error(
                f"Transition '{transition_name}' not found. Available: {available}"
            )
            return False

        await self._request(
            "POST",
            f"/issue/{issue_key}/transitions",
            json={"transition": {"id": target["id"]}},
        )
        logger.info(f"Transitioned {issue_key} to '{transition_name}'")
        return True

    async def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        """Add a comment to an issue (using ADF format)."""
        # Atlassian Document Format for plain text
        adf_body = {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": body}],
                }
            ],
        }
        return await self._request(
            "POST",
            f"/issue/{issue_key}/comment",
            json={"body": adf_body},
        )

    # --- Internal Helpers ---

    async def _get_comments(self, issue_key: str) -> list[dict[str, str]]:
        """Fetch comments for an issue."""
        try:
            result = await self._request("GET", f"/issue/{issue_key}/comment")
            comments = []
            for c in result.get("comments", []):
                comments.append(
                    {
                        "author": c.get("author", {}).get("displayName", "Unknown"),
                        "body": self._extract_text(c.get("body")),
                        "created": c.get("created", ""),
                    }
                )
            return comments
        except Exception:
            return []

    @staticmethod
    def _extract_text(adf_content: Any) -> str:
        """Extract plain text from Atlassian Document Format (ADF)."""
        if not adf_content:
            return ""
        if isinstance(adf_content, str):
            return adf_content

        texts = []

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("type") == "text":
                    texts.append(node.get("text", ""))
                for child in node.get("content", []):
                    _walk(child)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(adf_content)
        return "\n".join(texts)

    @staticmethod
    def _extract_acceptance_criteria(fields: dict[str, Any]) -> str:
        """Try to extract acceptance criteria from common custom field locations."""
        # Common custom field names for acceptance criteria
        for key in ["customfield_10029", "customfield_10030", "acceptance_criteria"]:
            value = fields.get(key)
            if value:
                if isinstance(value, str):
                    return value
                return JiraClient._extract_text(value)

        # Fall back: look in description for "Acceptance Criteria" section
        description = JiraClient._extract_text(fields.get("description"))
        if "acceptance criteria" in description.lower():
            parts = description.lower().split("acceptance criteria")
            if len(parts) > 1:
                return parts[1].strip()

        return ""

    @staticmethod
    def _extract_sprint(fields: dict[str, Any]) -> Optional[str]:
        """Extract current sprint name."""
        sprint = fields.get("sprint")
        if sprint and isinstance(sprint, dict):
            return sprint.get("name")
        # Some Jira configs use customfield for sprint
        sprint_field = fields.get("customfield_10020")
        if sprint_field and isinstance(sprint_field, list) and sprint_field:
            return sprint_field[-1].get("name")
        return None

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> Any:
        """Make an authenticated request to the Jira API."""
        if not self._client:
            raise RuntimeError("Jira client not connected. Call connect() first.")

        resp = await self._client.request(method, endpoint, params=params, json=json)

        if resp.status_code == 404:
            raise ValueError(f"Jira resource not found: {endpoint}")
        if resp.status_code == 401:
            raise PermissionError("Jira authentication failed — check your credentials")
        if resp.status_code == 403:
            raise PermissionError("Jira access denied — insufficient permissions")

        resp.raise_for_status()

        # POST transitions return 204 No Content
        if resp.status_code == 204:
            return {}

        return resp.json()
