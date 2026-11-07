"""Safe parser for Node ``package.json`` manifests (S26-001).

Only the root ``package.json`` is read; npm/pnpm are never executed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.services.dependency_parser import ParsedRequirement, RequirementKind

_SECTION_NAMES = ("dependencies", "devDependencies")
_EXACT_RE = re.compile(r"^v?(\d+(?:\.\d+){0,2}(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)$")
_VERSION_RE = re.compile(r"v?(\d+(?:\.\d+)*)")
_IGNORED_PREFIXES = (
    "file:",
    "link:",
    "portal:",
    "git+",
    "git://",
    "github:",
    "gitlab:",
    "bitbucket:",
    "http://",
    "https://",
    "npm:",
)


@dataclass(slots=True)
class NodeParseResult:
    """Parsed package.json packages plus a parse-level error."""

    packages: list[ParsedRequirement] = field(default_factory=list)
    manifest_found: bool = True
    error: str | None = None


def normalize_npm_name(name: str) -> str:
    """Npm names are lowercase; scoped names keep the leading @ and slash."""
    return name.strip().lower()


def parse_package_json(
    repo_path: Path,
    *,
    manifest_path: Path | None = None,
) -> NodeParseResult:
    """Parse one ``package.json`` without invoking npm or reading node_modules."""
    root = repo_path.resolve()
    manifest = (manifest_path or (root / "package.json")).resolve()
    if not _is_inside(manifest, root) or not manifest.is_file():
        return NodeParseResult(packages=[], manifest_found=False)

    manifest_rel = _display_path(root, manifest)
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        return NodeParseResult(error=f"{manifest_rel}: {exc}")

    if not isinstance(payload, dict):
        return NodeParseResult(error=f"{manifest_rel}: root must be an object")

    packages: list[ParsedRequirement] = []
    for section in _SECTION_NAMES:
        dependencies = payload.get(section)
        if not isinstance(dependencies, dict):
            continue
        for raw_name, raw_spec in dependencies.items():
            if not isinstance(raw_name, str) or not isinstance(raw_spec, str):
                continue
            name = normalize_npm_name(raw_name)
            if not name:
                continue
            kind, current = _parse_node_spec(raw_spec)
            packages.append(
                ParsedRequirement(
                    name=name,
                    declared=raw_spec.strip(),
                    kind=kind,
                    current=current,
                    manifest_line=None,
                    manifest_section=section,
                    manifest_path=manifest_rel,
                )
            )
    return NodeParseResult(packages=packages)


def _is_inside(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.name


def _parse_node_spec(spec: str) -> tuple[RequirementKind, str | None]:
    value = spec.strip()
    if not value:
        return "range", None
    lowered = value.lower()

    if lowered.startswith("workspace:"):
        return "workspace", None
    if lowered.startswith(("file:", "link:", "portal:")):
        return "path", None
    if lowered.startswith(_IGNORED_PREFIXES):
        return "vcs", None
    if lowered in {"*", "latest", "next", "beta", "canary", "rc"}:
        return "range", None

    exact = _EXACT_RE.match(value)
    if exact is not None:
        return "exact", exact.group(1)

    match = _VERSION_RE.search(value)
    if match is not None:
        return "range", match.group(1)
    return "range", None


__all__ = ["NodeParseResult", "normalize_npm_name", "parse_package_json"]
