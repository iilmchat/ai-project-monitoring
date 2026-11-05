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
    scan_roots: str = "C:/Projects"
    scan_depth: int = 3
    scan_ignore: str = "node_modules,.venv,vendor,dist,build,target"
    scan_concurrency: int = 4
    status_ttl_seconds: int = 60
    compare_ttl_seconds: int = 60
    fetch_timeout: int = 30
    debug: bool = False
    app_version: str = "0.1.0"

    @property
    def scan_root_paths(self) -> list[str]:
        """SCAN_ROOTS as a list of paths."""
        return _split_csv(self.scan_roots)

    @property
    def scan_ignore_names(self) -> list[str]:
        """SCAN_IGNORE as a list of directory names."""
        return _split_csv(self.scan_ignore)


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (useful for non-request contexts)."""
    return Settings()
