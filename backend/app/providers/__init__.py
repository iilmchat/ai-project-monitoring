"""Provider clients for GitHub and GitFlic (SPEC §3.8, ARCHITECTURE §7)."""

from __future__ import annotations

from app.providers.base import BranchResult, ProviderRepo
from app.providers.gitflic_client import GitFlicClient
from app.providers.github_client import GitHubClient

__all__ = ["BranchResult", "GitFlicClient", "GitHubClient", "ProviderRepo"]
