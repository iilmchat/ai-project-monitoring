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


def parse_package_json(repo_path: Path) -> NodeParseResult:
    """Parse root ``package.json`` without invoking npm or reading node_modules."""
    root = repo_path.resolve()
    manifest = root / "package.json"
    if not manifest.is_file():
        return NodeParseResult(packages=[], manifest_found=False)

    try:
        payload = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        return NodeParseResult(error=f"package.json: {exc}")

    if not isinstance(payload, dict):
        return NodeParseResult(error="package.json: root must be an object")

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
                )
            )
    return NodeParseResult(packages=packages)


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
