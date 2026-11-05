"""GitFlic REST API client (S9-003)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog

from app.providers.base import BranchResult, ProviderRepo

logger = structlog.get_logger(__name__)

GITFLIC_API = "https://gitflic.ru/api/v1"


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GitFlicClient:
    """Minimal read-only GitFlic REST client."""

    def __init__(
        self,
        token: str = "",
        *,
        timeout: float = 10.0,
        base_url: str = GITFLIC_API,
    ) -> None:
        self._token = token
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self._token)

    @property
    def provider(self) -> str:
        return "gitflic"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def get_branch(self, full_name: str, branch: str) -> BranchResult:
        if not self._token:
            return BranchResult(error="not_configured")

        # GitFlic exposes branches as a list; select the requested branch.
        url = f"{self._base_url}/project/{full_name}/branches"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            logger.warning("provider_error", provider="gitflic", error=str(exc))
            return BranchResult(error=str(exc))

        if response.status_code == 404:
            return BranchResult(sha=None, found=False)
        if response.status_code in {403, 429}:
            logger.warning(
                "provider_rate_limit",
                provider="gitflic",
                status_code=response.status_code,
            )
            return BranchResult(error="rate_limited", rate_limited=True)
        if response.status_code >= 400:
            logger.warning(
                "provider_error", provider="gitflic", status_code=response.status_code
            )
            return BranchResult(error=f"http_{response.status_code}")

        payload: Any = response.json()
        branches = payload if isinstance(payload, list) else payload.get("content", [])
        if not isinstance(branches, list):
            return BranchResult(error="invalid_response")

        for item in branches:
            if not isinstance(item, dict) or item.get("name") != branch:
                continue
            commit = item.get("commit") or {}
            sha = commit.get("sha") or commit.get("hash") or item.get("sha")
            date = _parse_date(commit.get("date") or item.get("date"))
            if sha:
                return BranchResult(sha=str(sha), date=date)
        return BranchResult(sha=None, found=False)

    async def get_branch_sha(self, full_name: str, branch: str) -> str | None:
        result = await self.get_branch(full_name, branch)
        return result.sha

    async def get_ci_status(self, full_name: str, branch: str) -> dict[str, object]:
        """GitFlic CI is not exposed by the public API yet (v0.2.0)."""
        return {
            "provider": "gitflic",
            "status": "not_supported",
            "conclusion": None,
            "url": None,
        }

    async def list_repos(self) -> list[dict[str, object]]:
        if not self._token:
            return []

        repos: list[dict[str, object]] = []
        url = f"{self._base_url}/projects"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    url, headers=self._headers(), params={"page": 0, "size": 100}
                )
        except httpx.HTTPError as exc:
            logger.warning("provider_error", provider="gitflic", error=str(exc))
            return repos

        if response.status_code in {403, 429}:
            logger.warning(
                "provider_rate_limit", provider="gitflic", status_code=response.status_code
            )
            return repos
        if response.status_code >= 400:
            logger.warning("provider_error", provider="gitflic", status_code=response.status_code)
            return repos

        data: object = response.json()
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("content", [])
        else:
            items = []
        if not isinstance(items, list):
            return repos

        for item in items:
            if not isinstance(item, dict):
                continue
            owner_raw = item.get("owner")
            owner: dict[Any, Any] = owner_raw if isinstance(owner_raw, dict) else {}
            alias = item.get("alias") or item.get("name") or ""
            owner_alias = owner.get("alias") or owner.get("login") or ""
            full_name = item.get("full_name") or (
                f"{owner_alias}/{alias}" if owner_alias else str(alias)
            )
            repo = ProviderRepo(
                provider="gitflic",
                full_name=full_name,
                private=bool(item.get("private", False)),
                default_branch=str(item.get("defaultBranch", "main")),
                url=item.get("url"),
            )
            repos.append(
                {
                    "provider": repo.provider,
                    "full_name": repo.full_name,
                    "private": repo.private,
                    "default_branch": repo.default_branch,
                    "url": repo.url,
                }
            )
        return repos


__all__ = ["GitFlicClient"]
