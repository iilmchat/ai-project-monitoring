"""Recommendation generation from canonical repository state (SPEC §3.7).

Recommendations are text only: IIRuchating never executes them in v0.1.0
(ADR-0003, ARCHITECTURE §6).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.repository import RepositoryStatusResponse


@dataclass(frozen=True, slots=True)
class Recommendation:
    action: str
    reason: str
    command: str
    category: str = "local"


def _branch(status: RepositoryStatusResponse) -> str:
    return status.branch or "main"


def generate_recommendations(status: RepositoryStatusResponse) -> list[Recommendation]:
    """Build a prioritized list of local recommendations for ``status``."""
    branch = _branch(status)
    remote = status.upstream or f"origin/{branch}"

    if status.state == "dirty":
        return [
            Recommendation(
                action="commit",
                reason="Есть незакоммиченные изменения. Закоммитьте их перед синхронизацией.",
                command='git add . && git commit -m "..."',
            ),
            Recommendation(
                action="stash",
                reason="Либо временно спрячьте изменения, чтобы обновить рабочую копию.",
                command="git stash",
            ),
        ]

    if status.state == "diverged":
        return [
            Recommendation(
                action="pull-rebase",
                reason="Истории разошлись: локальная и удалённая ветки содержат разные коммиты.",
                command=f"git pull --rebase origin {branch}",
            ),
            Recommendation(
                action="merge",
                reason="Альтернатива rebase — обычный merge удалённой ветки.",
                command=f"git merge {remote}",
            ),
        ]

    if status.state == "ahead":
        return [
            Recommendation(
                action="push",
                reason="Есть незапушенные коммиты.",
                command=f"git push origin {branch}",
            ),
        ]

    if status.state == "behind":
        return [
            Recommendation(
                action="pull",
                reason="Удалённая ветка впереди: подтяните новые коммиты.",
                command=f"git pull origin {branch}",
            ),
        ]

    if status.state == "no_upstream":
        return [
            Recommendation(
                action="set-upstream",
                reason="Нет tracking-ветки: назначьте upstream для текущей ветки.",
                command=f"git branch --set-upstream-to=origin/{branch} {branch}",
            ),
        ]

    # current / detached / error: no safe local recommendation in v0.1.0.
    return []


__all__ = ["Recommendation", "generate_recommendations"]
