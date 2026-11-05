"""Read-only audit: no destructive Git commands anywhere in backend/app (S5-003)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.schemas.repository import DirtyCountsResponse, RepositoryStatusResponse
from app.services.recommendation_service import generate_recommendations

APP_DIR = Path(__file__).resolve().parents[1] / "app"

FORBIDDEN_PATTERNS = (
    "reset --hard",
    "clean -fd",
    "clean -fdx",
    "checkout .",
    "branch -D",
    "push --force",
    "push -f",
)


def test_no_destructive_git_commands_in_app() -> None:
    assert APP_DIR.is_dir(), f"app directory not found: {APP_DIR}"

    offenders: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in text:
                offenders.append(f"{path.relative_to(APP_DIR)}: {pattern}")

    assert offenders == [], "destructive Git commands found: " + ", ".join(offenders)


def test_command_backend_only_uses_safe_subcommands() -> None:
    """The subprocess backend must only build fetch/rev-list commands."""
    source = (APP_DIR / "git" / "command_backend.py").read_text(encoding="utf-8")

    assert '["fetch", "--all", "--prune"]' in source
    assert '"rev-list"' in source
    for pattern in FORBIDDEN_PATTERNS:
        assert pattern not in source


@pytest.mark.parametrize(
    "state",
    ["current", "dirty", "diverged", "ahead", "behind", "no_upstream", "detached", "error"],
)
def test_recommendation_commands_are_non_destructive(state: str) -> None:
    status = RepositoryStatusResponse(
        repository_id=1,
        path="C:/work/repo",
        branch="main",
        upstream="origin/main",
        state=state,
        dirty=DirtyCountsResponse(modified=1 if state == "dirty" else 0),
        ahead=1 if state in {"ahead", "diverged"} else 0,
        behind=1 if state in {"behind", "diverged"} else 0,
        detached=state == "detached",
        remote_status="ok",
        checked_at="2026-11-05T00:00:00Z",
    )

    for recommendation in generate_recommendations(status):
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in recommendation.command
