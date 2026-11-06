"""Application settings loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Values are read from environment variables (case-insensitive) or a local
    ``.env`` file. Comma-separated list settings are stored as strings and
    exposed as parsed lists via properties: this keeps behaviour predictable
    with pydantic-settings (no JSON decoding required for env values).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = "sqlite+aiosqlite:///./data/iiruchating.db"
    scan_roots: str = "/projects"
    scan_depth: int = 3
    scan_ignore: str = "node_modules,.venv,vendor,dist,build,target"
    scan_concurrency: int = 4
    status_ttl_seconds: int = 60
    compare_ttl_seconds: int = 60
    fetch_timeout: int = 30
    github_token: str = ""
    gitflic_token: str = ""
    webhook_secret: str = ""
    mirror_poll_interval_seconds: int = 300
    mirror_status_ttl_seconds: int = 300
    provider_timeout_seconds: float = 10.0
    provider_cache_ttl_seconds: int = 60
    docker_enabled: bool = True
    docker_host: str = ""
    docker_path_map: str = ""
    docker_status_ttl_seconds: int = 30
    docker_timeout_seconds: float = 3.0
    dependency_cache_ttl_seconds: int = 86400
    dependency_check_concurrency: int = 4
    dependency_http_timeout: float = 5.0
    osv_api_url: str = "https://api.osv.dev"
    security_cache_ttl_seconds: int = 21600
    security_check_concurrency: int = 4
    security_http_timeout: float = 10.0
    secret_scan_enabled: bool = True
    secret_scan_max_files: int = 5000
    secret_scan_max_file_bytes: int = 1048576
    secret_scan_ttl_seconds: int = 300
    insights_cache_ttl_seconds: int = 300
    insights_git_timeout_seconds: float = 10.0
    insights_hotspots_limit: int = 5
    insights_hotspots_days: int = 90
    llm_enabled: bool = False
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_model: str = "qwen2.5-coder-7b-instruct"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 30.0
    llm_max_diff_chars: int = 10000
    llm_allow_remote: bool = False
    ai_cache_ttl_seconds: int = 604800
    global_analytics_cache_ttl_seconds: int = 3600
    global_analytics_limit: int = 50
    global_analytics_concurrency: int = 4
    action_timeout_seconds: int = 60
    notifications_enabled: bool = True
    default_canonical_provider: str = "github"
    notify_on: str = (
        "history_rewritten,missing_on_gitflic,missing_on_github,behind_gitflic"
    )
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    debug: bool = False
    app_version: str = "0.6.0"

    @property
    def scan_root_paths(self) -> list[str]:
        """SCAN_ROOTS as a list of paths."""
        return _split_csv(self.scan_roots)

    @property
    def scan_ignore_names(self) -> list[str]:
        """SCAN_IGNORE as a list of directory names."""
        return _split_csv(self.scan_ignore)

    @property
    def notify_on_names(self) -> list[str]:
        """NOTIFY_ON as a list of mirror statuses."""
        return _split_csv(self.notify_on)


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (useful for non-request contexts)."""
    return Settings()
