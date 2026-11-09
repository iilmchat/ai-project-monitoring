"""Settings schemas (S15-001, S43-001)."""

from __future__ import annotations

from pydantic import BaseModel


class SettingsStatusResponse(BaseModel):
    """First-run onboarding status (S50-001)."""

    is_configured: bool


class SettingsResponse(BaseModel):
    scan_roots: str
    github_token: str
    gitflic_token: str
    webhook_secret: str
    default_canonical_provider: str
    llm_enabled: bool = False
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_model: str = "qwen2.5-coder-7b-instruct"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 30
    llm_max_diff_chars: int = 10000
    llm_allow_remote: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    notifications_enabled: bool = True
    fetch_timeout: int = 30
    status_ttl_seconds: int = 60
    mirror_poll_interval_seconds: int = 300


class SettingsUpdate(BaseModel):
    scan_roots: str | None = None
    github_token: str | None = None
    gitflic_token: str | None = None
    webhook_secret: str | None = None
    default_canonical_provider: str | None = None
    llm_enabled: bool | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_timeout_seconds: int | None = None
    llm_max_diff_chars: int | None = None
    llm_allow_remote: bool | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    notifications_enabled: bool | None = None
    fetch_timeout: int | None = None
    status_ttl_seconds: int | None = None
    mirror_poll_interval_seconds: int | None = None


__all__ = ["SettingsResponse", "SettingsStatusResponse", "SettingsUpdate"]
