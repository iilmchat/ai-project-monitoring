"""Application settings loaded from environment variables / .env."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
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
    dependency_manifest_max_depth: int = 3
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
    sast_enabled: bool = True
    sast_timeout_seconds: float = 120.0
    sast_max_findings: int = 500
    sast_max_output_bytes: int = 8 * 1024 * 1024
    sast_cache_ttl_seconds: int = 86400
    sast_semgrep_config: str = ""
    llm_enabled: bool = False
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_model: str = "qwen2.5-coder-7b-instruct"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 30.0
    llm_max_diff_chars: int = 10000
    llm_allow_remote: bool = False
    ai_cache_ttl_seconds: int = 604800
    ai_prompt_version: str = "v1"
    ai_code_review_max_chars: int = 40000
    ai_code_review_chunk_chars: int = 5000
    ai_code_review_max_chunks: int = 8
    ai_conflict_max_file_bytes: int = 1048576
    ai_conflict_max_chars: int = 20000
    ai_conflict_max_blocks: int = 10
    ai_release_notes_max_commits: int = 500
    ai_release_notes_max_chars: int = 20000
    ai_chat_max_history: int = 10
    ai_chat_max_context_chars: int = 12000
    ai_chat_max_output_chars: int = 4000
    gigachat_oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_api_url: str = "https://gigachat.devices.sberbank.ru/api/v1"
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_ca_bundle: str = ""
    gigachat_token_refresh_margin_seconds: int = 60
    gigachat_timeout_seconds: float = 30.0
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_base_url: str = "http://127.0.0.1:1234/v1"
    embedding_api_key: str = ""
    embedding_allow_remote: bool = False
    embedding_batch_size: int = 32
    embedding_timeout_seconds: float = 30.0
    rag_max_file_bytes: int = 524288
    rag_max_chunks_per_repo: int = 2000
    rag_chunk_chars: int = 1000
    rag_chunk_overlap: int = 150
    auth_enabled: bool = True
    admin_username: str = "admin"
    admin_password: str = "admin"
    auth_jwt_secret: str = ""
    auth_token_ttl_seconds: int = 604800
    auth_login_rate_limit: int = 5
    auth_login_rate_window_seconds: int = 60
    global_analytics_cache_ttl_seconds: int = 3600
    global_analytics_limit: int = 50
    global_analytics_concurrency: int = 4
    dependency_update_timeout_seconds: int = 180
    dependency_update_max_output_chars: int = 10000
    action_timeout_seconds: int = 60
    notifications_enabled: bool = True
    default_canonical_provider: str = "github"
    notify_on: str = (
        "history_rewritten,missing_on_gitflic,missing_on_github,behind_gitflic"
    )
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    tauri_mode: bool = False
    tauri_data_dir: str = ""
    debug: bool = False
    app_version: str = "1.3.0"

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

    @model_validator(mode="after")
    def _apply_tauri_defaults(self) -> Settings:
        """Desktop mode always uses SQLite in the per-user app-data directory."""
        if not self.tauri_mode:
            return self
        data_dir = (
            Path(self.tauri_data_dir).expanduser()
            if self.tauri_data_dir
            else _default_tauri_data_dir()
        )
        data_dir.mkdir(parents=True, exist_ok=True)
        self.tauri_data_dir = str(data_dir)
        self.database_url = (
            f"sqlite+aiosqlite:///{(data_dir / 'iiruchating.db').as_posix()}"
        )
        if self.scan_roots.strip() in {"", "/projects"}:
            projects = Path.home() / "Projects"
            self.scan_roots = str(projects if projects.exists() else Path.home())
        return self


def _default_tauri_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    return base / "IIRuchating"


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (useful for non-request contexts)."""
    return Settings()
