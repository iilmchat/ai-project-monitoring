"""Safe README and repository document access (S35-002).

Only files inside the repository root are read. Raw HTML is never rendered by
the backend; the frontend uses a small safe Markdown renderer.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

MAX_DOCUMENT_BYTES = 512 * 1024
ALLOWED_SUFFIXES = frozenset({".md", ".markdown", ".txt"})
README_CANDIDATES = ("readme.md", "readme.markdown", "readme.txt")

_VERSION_LINE_RE = re.compile(
    r"(?:версия|version)\s*[:：]\s*[`*_ ]*"
    r"(v?\d+(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?)",
    re.IGNORECASE,
)
_BADGE_VERSION_RE = re.compile(
    r"(?:badge|shield)[^\n)]*?(?:version|версия)[-_ ]"
    r"(v?\d+(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?)",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^#\s+(.+?)\s*#*\s*$")
_INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_EMPHASIS_RE = re.compile(r"[*_]{1,3}([^*_]+)[*_]{1,3}")


class DocumentAccessError(ValueError):
    """Base class for safe document access failures."""


class DocumentNotFoundError(DocumentAccessError):
    """The requested document does not exist."""


class DocumentTooLargeError(DocumentAccessError):
    """The requested document exceeds the configured size limit."""


@dataclass(frozen=True, slots=True)
class ReadmeMetadata:
    path: str
    name: str
    version: str | None
    content: str


@dataclass(frozen=True, slots=True)
class RepositoryDocument:
    path: str
    content: str


def read_readme(repo_path: str | Path) -> ReadmeMetadata | None:
    """Find and parse the repository README, if one exists."""
    root = Path(repo_path).resolve()
    readme = _find_readme(root)
    if readme is None:
        return None
    content = _read_text(readme)
    name, version = parse_readme_metadata(content, fallback=root.name)
    return ReadmeMetadata(
        path=readme.relative_to(root).as_posix(),
        name=name,
        version=version,
        content=content,
    )


def read_document(repo_path: str | Path, relative_path: str) -> RepositoryDocument:
    """Read a Markdown/text document strictly inside ``repo_path``."""
    root = Path(repo_path).resolve()
    raw = (relative_path or "").strip().replace("\\", "/")
    if not raw:
        raise DocumentNotFoundError("document path is empty")
    if raw.startswith("/") or raw.startswith("~") or ".." in raw.split("/"):
        raise DocumentAccessError("document path must stay inside the repository")

    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise DocumentAccessError("document path must stay inside the repository") from exc
    if ".git" in candidate.relative_to(root).parts:
        raise DocumentAccessError("git metadata is not readable")
    if candidate.suffix.lower() not in ALLOWED_SUFFIXES:
        raise DocumentAccessError("only Markdown and text documents are supported")
    if not candidate.is_file():
        raise DocumentNotFoundError(f"document not found: {raw}")
    return RepositoryDocument(
        path=candidate.relative_to(root).as_posix(),
        content=_read_text(candidate),
    )


def parse_readme_metadata(content: str, *, fallback: str) -> tuple[str, str | None]:
    """Extract a human title and version from a README."""
    title: str | None = None
    version: str | None = None
    for line in content.splitlines()[:80]:
        stripped = line.strip()
        if title is None:
            heading = _HEADING_RE.match(stripped)
            if heading is not None:
                title = _clean_inline(heading.group(1)).strip()
        if version is None:
            match = _VERSION_LINE_RE.search(stripped) or _BADGE_VERSION_RE.search(stripped)
            if match is not None:
                version = match.group(1).rstrip(".,;")
    return (title or fallback, version)


def _find_readme(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    try:
        entries = list(os.scandir(root))
    except OSError:
        return None
    files = {
        entry.name.lower(): Path(entry.path)
        for entry in entries
        if entry.is_file(follow_symlinks=False)
    }
    for candidate in README_CANDIDATES:
        path = files.get(candidate)
        if path is not None:
            return path
    return None


def _read_text(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise DocumentNotFoundError(str(exc)) from exc
    if size > MAX_DOCUMENT_BYTES:
        raise DocumentTooLargeError(
            f"document is larger than {MAX_DOCUMENT_BYTES} bytes"
        )
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise DocumentNotFoundError(str(exc)) from exc


def _clean_inline(value: str) -> str:
    cleaned = _INLINE_LINK_RE.sub(r"\1", value)
    cleaned = _INLINE_CODE_RE.sub(r"\1", cleaned)
    cleaned = _EMPHASIS_RE.sub(r"\1", cleaned)
    return cleaned.strip()


__all__ = [
    "ALLOWED_SUFFIXES",
    "MAX_DOCUMENT_BYTES",
    "DocumentAccessError",
    "DocumentNotFoundError",
    "DocumentTooLargeError",
    "ReadmeMetadata",
    "RepositoryDocument",
    "parse_readme_metadata",
    "read_document",
    "read_readme",
]
