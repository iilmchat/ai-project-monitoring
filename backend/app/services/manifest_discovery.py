"""Safe discovery and merging of dependency manifests (S35-001, S57-001).

The service walks a repository only to locate known manifest files. It never
executes package managers and never follows symlinks. Ignored directories are
pruned early so ``node_modules``, ``bin``/``obj`` and virtualenvs do not affect
performance.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.services.dependency_parser import (
    ParsedRequirement,
    RequirementsParseResult,
    parse_requirements,
)
from app.services.dotnet_parser import (
    PROJECT_SUFFIXES,
    DotnetParseResult,
    is_dotnet_manifest,
    parse_dotnet_manifest,
    to_requirement,
)
from app.services.node_parser import NodeParseResult, parse_package_json

Ecosystem = str

DEFAULT_IGNORED_DIRS = frozenset(
    {
        "node_modules",
        "bower_components",
        ".venv",
        "venv",
        "env",
        ".env",
        "virtualenv",
        ".git",
        ".hg",
        ".svn",
        "dist",
        "build",
        "target",
        "bin",
        "obj",
        ".vs",
        "packages",
        "vendor",
        "coverage",
        "htmlcov",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".next",
        ".nuxt",
        ".turbo",
        ".cache",
    }
)

MANIFEST_ECOSYSTEMS: dict[str, tuple[str, str]] = {
    "requirements.txt": ("python", "python"),
    "package.json": ("node", "node"),
    "packages.config": ("dotnet", "dotnet"),
}


@dataclass(frozen=True, slots=True)
class DiscoveredManifests:
    """Manifest paths grouped by ecosystem, relative to the repository root."""

    root: Path
    python: tuple[Path, ...] = ()
    node: tuple[Path, ...] = ()
    dotnet: tuple[Path, ...] = ()

    def for_ecosystem(self, ecosystem: str) -> tuple[Path, ...]:
        if ecosystem == "python":
            return self.python
        if ecosystem == "node":
            return self.node
        if ecosystem == "dotnet":
            return self.dotnet
        return ()

    @property
    def all_paths(self) -> tuple[Path, ...]:
        return self.python + self.node + self.dotnet


def discover_manifests(
    repo_path: Path | str,
    *,
    max_depth: int = 3,
    ignored_dirs: Iterable[str] | None = None,
) -> DiscoveredManifests:
    """Find known manifest files up to ``max_depth`` below the repository root.

    Depth 0 is the repository root. Directories in ``ignored_dirs`` and hidden
    directories are pruned. Results are deterministic (sorted by path).
    """
    root = Path(repo_path).resolve()
    if not root.is_dir():
        return DiscoveredManifests(root=root)

    ignored = DEFAULT_IGNORED_DIRS | {
        item.strip().lower()
        for item in (ignored_dirs or ())
        if item.strip()
    }
    found: dict[str, list[Path]] = {"python": [], "node": [], "dotnet": []}
    stack: list[tuple[Path, int]] = [(root, 0)]

    while stack:
        current, level = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue

        for entry in entries:
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
            except OSError:
                continue
            mapping = MANIFEST_ECOSYSTEMS.get(entry.name.lower())
            if mapping is not None:
                found[mapping[0]].append(Path(entry.path))
            elif is_dotnet_manifest(Path(entry.path)) and entry.name.lower().endswith(
                PROJECT_SUFFIXES
            ):
                found["dotnet"].append(Path(entry.path))

        if level >= max_depth:
            continue

        for entry in entries:
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            name = entry.name.lower()
            if name in ignored or name.startswith("."):
                continue
            stack.append((Path(entry.path), level + 1))

    return DiscoveredManifests(
        root=root,
        python=tuple(sorted(found["python"], key=_sort_key)),
        node=tuple(sorted(found["node"], key=_sort_key)),
        dotnet=tuple(sorted(found["dotnet"], key=_sort_key)),
    )


def relative_path(root: Path, path: Path) -> str:
    """Return a POSIX-style path relative to ``root`` for API responses."""
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.name


def _sort_key(path: Path) -> tuple[int, str]:
    # Root manifests first, then nested ones alphabetically.
    depth = len(path.parts)
    return (depth, path.as_posix().lower())


_KIND_RANK = {
    "ignored": 0,
    "workspace": 0,
    "vcs": 0,
    "path": 0,
    "range": 1,
    "exact": 2,
}


def merge_requirements(
    requirements: Iterable[ParsedRequirement],
) -> list[ParsedRequirement]:
    """Merge declarations from several manifests, keeping one per package.

    A pinned declaration wins over a range; a range with a concrete lower bound
    wins over a range without one. Ties keep the first (sorted) manifest.
    """
    merged: dict[str, ParsedRequirement] = {}
    for requirement in requirements:
        key = requirement.name.lower()
        current = merged.get(key)
        if current is None:
            merged[key] = requirement
            continue
        new_rank = _KIND_RANK.get(requirement.kind, 0)
        old_rank = _KIND_RANK.get(current.kind, 0)
        if new_rank > old_rank or (
            new_rank == old_rank
            and requirement.current is not None
            and current.current is None
        ):
            merged[key] = requirement
    return list(merged.values())


@dataclass(slots=True)
class CombinedParseResult:
    """Parsed packages from every manifest of one ecosystem."""

    packages: list[ParsedRequirement]
    manifests: list[str]
    errors: list[str]
    manifest_found: bool

    @property
    def manifest_label(self) -> str | None:
        if not self.manifests:
            return None
        return self.manifests[0] if len(self.manifests) == 1 else ", ".join(self.manifests)


def parse_python_manifests(
    discovered: DiscoveredManifests,
    *,
    max_include_depth: int = 3,
) -> CombinedParseResult:
    """Parse all discovered ``requirements.txt`` files and merge packages."""
    packages: list[ParsedRequirement] = []
    manifests: list[str] = []
    errors: list[str] = []
    for path in discovered.python:
        parsed: RequirementsParseResult = parse_requirements(
            discovered.root,
            manifest_path=path,
            max_include_depth=max_include_depth,
        )
        if not parsed.manifest_found:
            continue
        manifests.append(relative_path(discovered.root, path))
        if parsed.error is not None:
            errors.append(parsed.error)
            continue
        packages.extend(parsed.packages)
    return CombinedParseResult(
        packages=merge_requirements(packages),
        manifests=manifests,
        errors=errors,
        manifest_found=bool(manifests),
    )


def parse_node_manifests(discovered: DiscoveredManifests) -> CombinedParseResult:
    """Parse all discovered ``package.json`` files and merge packages."""
    packages: list[ParsedRequirement] = []
    manifests: list[str] = []
    errors: list[str] = []
    for path in discovered.node:
        parsed: NodeParseResult = parse_package_json(discovered.root, manifest_path=path)
        if not parsed.manifest_found:
            continue
        manifests.append(relative_path(discovered.root, path))
        if parsed.error is not None:
            errors.append(parsed.error)
            continue
        packages.extend(parsed.packages)
    return CombinedParseResult(
        packages=merge_requirements(packages),
        manifests=manifests,
        errors=errors,
        manifest_found=bool(manifests),
    )


def parse_dotnet_manifests(discovered: DiscoveredManifests) -> CombinedParseResult:
    """Parse all discovered .NET projects and merge packages.

    ``Directory.Packages.props`` is resolved per project (nearest ancestor), so
    Central Package Management versions are applied without MSBuild. The props
    file is added to ``manifests`` so the UI can show the CPM badge.
    """
    packages: list[ParsedRequirement] = []
    manifests: list[str] = []
    errors: list[str] = []
    for path in discovered.dotnet:
        parsed: DotnetParseResult = parse_dotnet_manifest(
            discovered.root,
            manifest_path=path,
        )
        if not parsed.manifest_found:
            continue
        manifests.append(relative_path(discovered.root, path))
        if parsed.central_packages_file is not None:
            manifests.append(parsed.central_packages_file)
        if parsed.error is not None:
            errors.append(parsed.error)
        packages.extend(to_requirement(item) for item in parsed.packages)
    return CombinedParseResult(
        packages=merge_requirements(packages),
        manifests=list(dict.fromkeys(manifests)),
        errors=errors,
        manifest_found=bool(manifests),
    )


__all__ = [
    "DEFAULT_IGNORED_DIRS",
    "CombinedParseResult",
    "DiscoveredManifests",
    "discover_manifests",
    "merge_requirements",
    "parse_dotnet_manifests",
    "parse_node_manifests",
    "parse_python_manifests",
    "relative_path",
]
