"""Basic regex secret scanner for the working directory (S28-002).

Only the working tree is read (never Git history). Full secret values are
discarded immediately: the API receives a masked preview only.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from app.core.subprocess_flags import WINDOWS_CREATION_FLAGS
from app.schemas.security import (
    SecretConfidence,
    SecretFinding,
    SecretScanReport,
    SecretSeverity,
    SecretType,
)

IGNORE_MARKER = "iiruchating:ignore-secret"
IGNORE_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "vendor",
        "dist",
        "build",
        "target",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".next",
        ".turbo",
    }
)
MAX_FINDINGS = 200


@dataclass(frozen=True, slots=True)
class SecretRule:
    """One fixed detection rule."""

    type: SecretType
    pattern: re.Pattern[str]
    severity: SecretSeverity
    confidence: SecretConfidence
    value_group: str | None = None


RULES: tuple[SecretRule, ...] = (
    SecretRule(
        type="aws_access_key",
        pattern=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        severity="high",
        confidence="high",
    ),
    SecretRule(
        type="aws_secret_key",
        pattern=re.compile(
            r"(?i)aws_secret_access_key\s*[:=]\s*[\"']?(?P<value>[A-Za-z0-9/+=]{40})[\"']?"
        ),
        severity="high",
        confidence="medium",
        value_group="value",
    ),
    SecretRule(
        type="github_token",
        pattern=re.compile(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{82})\b"
        ),
        severity="high",
        confidence="high",
    ),
    SecretRule(
        type="jwt",
        pattern=re.compile(
            r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
        ),
        severity="medium",
        confidence="medium",
    ),
    SecretRule(
        type="private_key",
        pattern=re.compile(
            r"-----BEGIN (?:RSA|OPENSSH|EC|PGP) PRIVATE KEY(?: BLOCK)?-----"
        ),
        severity="high",
        confidence="high",
    ),
)


def mask_secret(value: str) -> str:
    """Return a short masked preview; never expose the full value."""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def redact_secrets(text: str) -> str:
    """Mask known secret patterns in free-form text (e.g. a git diff)."""
    redacted = text
    for rule in RULES:
        def replace(match: re.Match[str], rule: SecretRule = rule) -> str:
            secret = (
                match.group(rule.value_group)
                if rule.value_group is not None
                else match.group(0)
            )
            return match.group(0).replace(secret, mask_secret(secret), 1)

        redacted = rule.pattern.sub(replace, redacted)
    return redacted


def scan_secrets(
    repo_path: str,
    *,
    max_files: int = 5000,
    max_file_bytes: int = 1_048_576,
    max_findings: int = MAX_FINDINGS,
) -> SecretScanReport:
    """Scan tracked/untracked working-tree files for potential secrets."""
    root = Path(repo_path).resolve()
    if not root.is_dir():
        return SecretScanReport(status="unavailable", error="repository_not_found")

    files = _iter_candidates(root)
    findings: list[SecretFinding] = []
    seen: set[tuple[str, int, str, str]] = set()
    scanned = 0
    considered = 0
    truncated = False
    incomplete = False

    for path in files:
        if considered >= max(max_files, 1):
            truncated = True
            break
        considered += 1

        relative = _relative_to(path, root)
        if relative is None or path.is_symlink():
            continue
        try:
            if path.stat().st_size > max_file_bytes:
                incomplete = True
                continue
            data = path.read_bytes()
        except OSError:
            incomplete = True
            continue

        if b"\x00" in data[:8192]:
            continue
        scanned += 1
        text = data.decode("utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if IGNORE_MARKER in line:
                continue
            for rule in RULES:
                for match in rule.pattern.finditer(line):
                    secret = (
                        match.group(rule.value_group)
                        if rule.value_group is not None
                        else match.group(0)
                    )
                    preview = mask_secret(secret)
                    key = (relative, line_number, rule.type, preview)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(
                        SecretFinding(
                            file=relative,
                            line=line_number,
                            type=rule.type,
                            severity=rule.severity,
                            confidence=rule.confidence,
                            preview=preview,
                        )
                    )
                    if len(findings) >= max_findings:
                        truncated = True
                        break
                if len(findings) >= max_findings:
                    break
            if len(findings) >= max_findings:
                break
        if len(findings) >= max_findings:
            break

    status = "partial" if truncated or incomplete else "ok"
    return SecretScanReport(
        status=status,
        files_scanned=scanned,
        truncated=truncated,
        findings=findings,
    )


def _iter_candidates(root: Path) -> Iterator[Path]:
    listed = _git_listed_files(root)
    if listed is not None:
        yield from listed
        return
    yield from _walk_files(root)


def _git_listed_files(root: Path) -> list[Path] | None:
    """Return tracked + untracked non-ignored files, or ``None`` outside Git."""
    try:
        process = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "-co",
                "--exclude-standard",
            ],
            check=False,
            capture_output=True,
            timeout=5,
            creationflags=WINDOWS_CREATION_FLAGS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if process.returncode != 0:
        return None

    entries = process.stdout.decode("utf-8", errors="replace").split("\0")
    files: list[Path] = []
    for entry in entries:
        if not entry:
            continue
        candidate = root / entry
        if _is_ignored(candidate, root):
            continue
        files.append(candidate)
    return files


def _walk_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name for name in dirnames if name.lower() not in IGNORE_DIRS
        )
        for name in sorted(filenames):
            yield Path(dirpath) / name


def _is_ignored(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    return any(part.lower() in IGNORE_DIRS for part in relative.parts[:-1])


def _relative_to(path: Path, root: Path) -> str | None:
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return relative.as_posix()


__all__ = [
    "IGNORE_DIRS",
    "IGNORE_MARKER",
    "RULES",
    "SecretRule",
    "mask_secret",
    "redact_secrets",
    "scan_secrets",
]
