"""README and repository document schemas (S35-002)."""

from __future__ import annotations

from pydantic import BaseModel


class ReadmeResponse(BaseModel):
    """Parsed README metadata plus raw Markdown for the viewer."""

    repository_id: int
    path: str
    name: str
    version: str | None = None
    content: str


class RepositoryDocResponse(BaseModel):
    """One Markdown/text document from inside a repository."""

    repository_id: int
    path: str
    content: str


__all__ = ["ReadmeResponse", "RepositoryDocResponse"]
