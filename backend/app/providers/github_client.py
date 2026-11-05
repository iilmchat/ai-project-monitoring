"""GitHub REST API client (S9-002)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog

from app.providers.base import BranchResult, ProviderRepo
from app.providers.cache import TTLCache

logger = structlog.get_logger(__name__)

GITHUB_API = "https://api.github.com"


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GitHubClient:
    """Minimal read-only GitHub REST client."""

    def __init__(
        self,
        token: str = "",
        *,
        timeout: float = 10.0,
        base_url: str = GITHUB_API,
        cache_ttl_seconds: int = 60,
    ) -> None:
        self._token = token
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._cache = TTLCache(cache_ttl_seconds)

    @property
    def configured(self) -> bool:
        return bool(self._token)

    @property
    def provider(self) -> str:
        return "github"

    def set_token(self, token: str) -> None:
        self._token = token
        self._cache.clear()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def get_branch(self, full_name: str, branch: str) -> BranchResult:
        if not self._token:
            return BranchResult(error="not_configured")

        cache_key = f"github:{full_name}:{branch}"
        cached = self._cache.get(cache_key)
        if isinstance(cached, BranchResult):
            return cached

        url = f"{self._base_url}/repos/{full_name}/branches/{branch}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            logger.warning("provider_error", provider="github", error=str(exc))
            return BranchResult(error=str(exc))

        if response.status_code == 404:
            return BranchResult(sha=None, found=False)
        if response.status_code in {403, 429}:
            logger.warning(
                "provider_rate_limit",
                provider="github",
                status_code=response.status_code,
                remaining=response.headers.get("x-ratelimit-remaining"),
            )
            return BranchResult(error="rate_limited", rate_limited=True)
        if response.status_code >= 400:
            logger.warning(
                "provider_error", provider="github", status_code=response.status_code
            )
            return BranchResult(error=f"http_{response.status_code}")

        data: dict[str, Any] = response.json()
        commit = data.get("commit") or {}
        sha = commit.get("sha") or data.get("sha")
        nested = commit.get("commit") or {}
        date = _parse_date(nested.get("committer", {}).get("date"))
        if not sha:
            return BranchResult(error="invalid_response")
        result = BranchResult(sha=str(sha), date=date)
        self._cache.set(cache_key, result)
        return result

    async def get_branch_sha(self, full_name: str, branch: str) -> str | None:
        result = await self.get_branch(full_name, branch)
        return result.sha

    async def get_ci_status(self, full_name: str, branch: str) -> dict[str, object]:
        if not self._token:
            return {
                "provider": "github",
                "status": "not_configured",
                "conclusion": None,
                "url": None,
            }

        url = f"{self._base_url}/repos/{full_name}/actions/runs"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    url,
                    headers=self._headers(),
                    params={"branch": branch, "per_page": 1},
                )
        except httpx.HTTPError as exc:
            logger.warning("provider_error", provider="github", error=str(exc))
            return {
                "provider": "github",
                "status": "unavailable",
                "conclusion": None,
                "url": None,
            }

        if response.status_code in {403, 429}:
            logger.warning(
                "provider_rate_limit", provider="github", status_code=response.status_code
            )
            return {
                "provider": "github",
                "status": "unavailable",
                "conclusion": None,
                "url": None,
            }
        if response.status_code == 404:
            return {
                "provider": "github",
                "status": "not_supported",
                "conclusion": None,
                "url": None,
            }
        if response.status_code >= 400:
            logger.warning(
                "provider_error", provider="github", status_code=response.status_code
            )
            return {
                "provider": "github",
                "status": "unavailable",
                "conclusion": None,
                "url": None,
            }

        payload: Any = response.json()
        runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not runs:
            return {
                "provider": "github",
                "status": "none",
                "conclusion": None,
                "url": None,
            }
        run = runs[0]
        return {
            "provider": "github",
            "status": run.get("status") or "unknown",
            "conclusion": run.get("conclusion"),
            "url": run.get("html_url"),
        }

    async def list_repos(self) -> list[dict[str, object]]:
        if not self._token:
            return []

        cached = self._cache.get("github:list")
        if isinstance(cached, list):
            return cached

        repos: list[dict[str, object]] = []
        for page in range(1, 4):
            url = f"{self._base_url}/user/repos"
            params: dict[str, str | int] = {
                "per_page": 100,
                "page": page,
                "affiliation": "owner,collaborator,organization_member",
            }
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, headers=self._headers(), params=params)
            except httpx.HTTPError as exc:
                logger.warning("provider_error", provider="github", error=str(exc))
                break

            if response.status_code in {403, 429}:
                logger.warning(
                    "provider_rate_limit", provider="github", status_code=response.status_code
                )
                break
            if response.status_code >= 400:
                logger.warning(
                    "provider_error", provider="github", status_code=response.status_code
                )
                break

            batch = response.json()
            if not isinstance(batch, list) or not batch:
                break
            for item in batch:
                repo = ProviderRepo(
                    provider="github",
                    full_name=str(item.get("full_name", "")),
                    private=bool(item.get("private", False)),
                    default_branch=str(item.get("default_branch", "main")),
                    url=item.get("html_url"),
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
            if len(batch) < 100:
                break
        self._cache.set("github:list", repos)
        return repos


__all__ = ["GitHubClient"]
