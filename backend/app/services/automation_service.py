"""Generate Dependabot/Renovate configs without writing or pushing (S59-002)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.services.manifest_discovery import (
    DiscoveredManifests,
    discover_manifests,
    relative_path,
)

AutomationTool = Literal["dependabot", "renovate"]

_DEPENDABOT_ECOSYSTEM = {
    "python": "pip",
    "node": "npm",
    "dotnet": "nuget",
}
_RENOVATE_MANAGER = {
    "python": "pip_requirements",
    "node": "npm",
    "dotnet": "nuget",
}


@dataclass(frozen=True, slots=True)
class AutomationConfig:
    tool: AutomationTool
    path: str
    content: str
    content_hash: str
    ecosystems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AutomationService:
    """Build config text from discovered manifests; never modify the repo."""

    def generate(self, repo_path: str, tool: AutomationTool) -> AutomationConfig:
        root = Path(repo_path).resolve()
        discovered = discover_manifests(root)
        entries = _entries(discovered)
        ecosystems = sorted({ecosystem for ecosystem, _ in entries})
        warnings: list[str] = []
        if not entries:
            warnings.append("no_manifests")

        if tool == "dependabot":
            content = _dependabot(entries)
            path = ".github/dependabot.yml"
        else:
            content = _renovate(ecosystems)
            path = "renovate.json"

        return AutomationConfig(
            tool=tool,
            path=path,
            content=content,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            ecosystems=ecosystems,
            warnings=warnings,
        )


def _entries(discovered: DiscoveredManifests) -> list[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    root = discovered.root
    for ecosystem, paths in (
        ("python", discovered.python),
        ("node", discovered.node),
        ("dotnet", discovered.dotnet),
    ):
        for path in paths:
            directory = Path(relative_path(root, path)).parent.as_posix()
            result.add((ecosystem, "/" if directory in {"", "."} else f"/{directory}"))
    return sorted(result)


def _dependabot(entries: list[tuple[str, str]]) -> str:
    lines = ["version: 2", "updates:"]
    if not entries:
        return "\n".join([*lines, "  []", ""])
    for ecosystem, directory in entries:
        lines.extend(
            [
                f"  - package-ecosystem: {_DEPENDABOT_ECOSYSTEM[ecosystem]}",
                f"    directory: {directory}",
                "    schedule:",
                "      interval: weekly",
                "    open-pull-requests-limit: 5",
                "    groups:",
                "      minor-and-patch:",
                "        patterns:",
                '          - "*"',
                "        update-types:",
                '          - "minor"',
                '          - "patch"',
            ]
        )
    return "\n".join([*lines, ""])


def _renovate(ecosystems: list[str]) -> str:
    managers = sorted(
        {_RENOVATE_MANAGER[item] for item in ecosystems if item in _RENOVATE_MANAGER}
    )
    config: dict[str, object] = {
        "$schema": "https://docs.renovatebot.com/renovate-schema.json",
        "extends": ["config:recommended"],
        "schedule": ["before 6am on monday"],
        "packageRules": [
            {
                "matchUpdateTypes": ["minor", "patch"],
                "groupName": "minor and patch dependencies",
            }
        ],
    }
    if managers:
        config["enabledManagers"] = managers
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


__all__ = ["AutomationConfig", "AutomationService", "AutomationTool"]
