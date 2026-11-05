"""Safe parser for Python ``requirements.txt`` manifests (S25-002).

Only files inside the repository root are read; pip is never executed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

RequirementKind = Literal["exact", "range", "vcs", "path", "workspace"]

_NAME_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*(?:\[[^\]]*\])?\s*(.*)$"
)
_SPECIFIER_RE = re.compile(r"(===|==|~=|>=|<=|!=|>|<)\s*([^,\s]+)")
_HASH_RE = re.compile(r"\s+--hash(?:=\S+)?")
_URL_PREFIXES = (
    "git+",
    "hg+",
    "svn+",
    "bzr+",
    "http://",
    "https://",
    "file:",
    "./",
    "../",
    "~/",
)


@dataclass(frozen=True, slots=True)
class ParsedRequirement:
    """One requirement declaration from a manifest."""

    name: str
    declared: str
    kind: RequirementKind
    current: str | None
    manifest_line: int | None = None


@dataclass(slots=True)
class RequirementsParseResult:
    """Parsed packages plus a parse-level error, if any."""

    packages: list[ParsedRequirement] = field(default_factory=list)
    manifest_found: bool = True
    error: str | None = None


def normalize_package_name(name: str) -> str:
    """PEP 503-style normalisation used for cache keys and registry URLs."""
    return re.sub(r"[-_.]+", "-", name.strip()).lower().strip("-")


def parse_requirements(
    repo_path: Path,
    *,
    max_include_depth: int = 3,
) -> RequirementsParseResult:
    """Parse ``requirements.txt`` in ``repo_path`` without running pip."""
    root = repo_path.resolve()
    manifest = root / "requirements.txt"
    if not manifest.is_file():
        return RequirementsParseResult(packages=[], manifest_found=False)

    result = RequirementsParseResult()
    visited: set[Path] = set()
    try:
        _parse_file(
            manifest,
            root=root,
            depth=0,
            max_depth=max_include_depth,
            visited=visited,
            result=result,
        )
    except OSError as exc:
        result.error = f"requirements.txt: {exc}"
    return result


def _parse_file(
    path: Path,
    *,
    root: Path,
    depth: int,
    max_depth: int,
    visited: set[Path],
    result: RequirementsParseResult,
) -> None:
    resolved = path.resolve()
    if resolved in visited:
        return
    visited.add(resolved)

    try:
        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        # A missing include must not hide the main manifest. The caller gets a
        # partial report; the UI can still show the packages that were read.
        return

    index = 0
    while index < len(lines):
        start_line = index + 1
        line = lines[index].strip()
        index += 1

        while line.endswith("\\") and index < len(lines):
            continuation = lines[index].strip()
            index += 1
            line = f"{line[:-1].rstrip()} {continuation}"

        if not line or line.startswith("#"):
            continue

        line = _strip_inline_comment(line)
        if not line:
            continue

        if line.startswith(("-r ", "--requirement ")):
            include_raw = line.split(maxsplit=1)[1].strip().strip("'\"")
            if not include_raw or depth >= max_depth:
                continue
            include_path = (resolved.parent / include_raw).resolve()
            if not _is_inside(include_path, root) or not include_path.is_file():
                continue
            _parse_file(
                include_path,
                root=root,
                depth=depth + 1,
                max_depth=max_depth,
                visited=visited,
                result=result,
            )
            continue

        if line.startswith(("-c ", "--constraint ")):
            # Constraints restrict versions but do not declare dependencies.
            continue

        if line.startswith(("-e ", "--editable ")):
            target = line.split(maxsplit=1)[1].strip()
            result.packages.append(
                ParsedRequirement(
                    name=_ignored_name(target),
                    declared=line,
                    kind=_ignored_kind(target),
                    current=None,
                    manifest_line=start_line,
                )
            )
            continue

        if line.startswith("-"):
            # --index-url, --extra-index-url, --hash, etc. are not packages.
            continue

        if line.startswith(_URL_PREFIXES):
            result.packages.append(
                ParsedRequirement(
                    name=_ignored_name(line),
                    declared=line,
                    kind=_ignored_kind(line),
                    current=None,
                    manifest_line=start_line,
                )
            )
            continue

        parsed = _parse_standard_requirement(line, manifest_line=start_line)
        if parsed is not None:
            result.packages.append(parsed)


def _strip_inline_comment(line: str) -> str:
    """Strip a trailing pip comment while preserving URL fragments."""
    match = re.search(r"\s+#", line)
    if match is None:
        return line.strip()
    return line[: match.start()].strip()


def _is_inside(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _parse_standard_requirement(
    line: str,
    *,
    manifest_line: int,
) -> ParsedRequirement | None:
    requirement = line.split(";", 1)[0].strip()
    if not requirement:
        return None

    if "@" in requirement and not requirement.startswith(("http://", "https://")):
        name_part, reference = requirement.split("@", 1)
        name = normalize_package_name(name_part)
        if not name:
            return None
        return ParsedRequirement(
            name=name,
            declared=line,
            kind=_ignored_kind(reference.strip()),
            current=None,
            manifest_line=manifest_line,
        )

    match = _NAME_RE.match(requirement)
    if match is None:
        return None
    name = normalize_package_name(match.group(1))
    if not name:
        return None

    spec = _HASH_RE.sub("", match.group(2)).strip()
    kind, current = _parse_specifiers(spec)
    return ParsedRequirement(
        name=name,
        declared=line,
        kind=kind,
        current=current,
        manifest_line=manifest_line,
    )


def _parse_specifiers(spec: str) -> tuple[RequirementKind, str | None]:
    matches = _SPECIFIER_RE.findall(spec)
    if not matches:
        return "range", None

    exact = (
        len(matches) == 1
        and matches[0][0] == "=="
        and "*" not in matches[0][1]
    )
    current: str | None = None
    for operator, version in matches:
        if operator in {"==", ">=", ">", "~="}:
            candidate = version.rstrip("*").rstrip(".").strip()
            if candidate:
                current = candidate
                break
    return ("exact" if exact else "range"), current


def _ignored_kind(reference: str) -> RequirementKind:
    lowered = reference.lower()
    if any(token in lowered for token in ("git+", "hg+", "svn+", "bzr+")):
        return "vcs"
    return "path"


def _ignored_name(reference: str) -> str:
    if "#egg=" in reference:
        egg = reference.split("#egg=", 1)[1].split("&", 1)[0]
        normalized = normalize_package_name(egg)
        if normalized:
            return normalized
    cleaned = reference.split("#", 1)[0].rstrip("/")
    candidate = cleaned.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    candidate = candidate.removesuffix(".git")
    normalized = normalize_package_name(candidate)
    return normalized or "editable"


__all__ = [
    "ParsedRequirement",
    "RequirementKind",
    "RequirementsParseResult",
    "normalize_package_name",
    "parse_requirements",
]
