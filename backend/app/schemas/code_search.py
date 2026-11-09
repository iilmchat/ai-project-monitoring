"""Schemas for RAG code search (SPEC §3.26, S44)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CodeSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    repository_ids: list[int] | None = None
    limit: int = Field(default=5, ge=1, le=50)
    min_score: float = Field(default=0.2, ge=0.0, le=1.0)
    language: str | None = Field(default=None, max_length=32)


class CodeSearchResult(BaseModel):
    repository_id: int
    repository_name: str
    path: str
    start_line: int
    end_line: int
    language: str
    snippet: str
    score: float
    url: str | None = None


class CodeSearchResponse(BaseModel):
    query: str
    model: str
    took_ms: float
    indexed_repositories: int
    stale: bool
    results: list[CodeSearchResult] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)
    repository_ids: list[int] | None = None
    limit: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.2, ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    citations: list[CodeSearchResult] = Field(default_factory=list)
    model: str
    embedding_model: str
    took_ms: float


class CodeIndexRequest(BaseModel):
    repository_ids: list[int] | None = None
    force: bool = False


class CodeIndexJob(BaseModel):
    status: Literal["started", "running", "completed", "failed"] = "started"
    message: str | None = None
    started_at: datetime


class CodeIndexStatus(BaseModel):
    indexed_repositories: int = 0
    indexed_chunks: int = 0
    last_indexed_at: datetime | None = None
    running: bool = False
    errors: list[str] = Field(default_factory=list)


__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "CodeIndexJob",
    "CodeIndexRequest",
    "CodeIndexStatus",
    "CodeSearchRequest",
    "CodeSearchResponse",
    "CodeSearchResult",
]
