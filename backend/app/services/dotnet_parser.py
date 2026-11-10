"""Safe parsers for .NET manifests (S57-001).

Only XML/JSON-like manifests inside the repository root are read. MSBuild is
never evaluated and ``dotnet`` is never executed here. Unresolvable versions
(``$(Property)``, conditional items) are reported as ``unknown`` instead of
being guessed.

Supported formats:

* SDK-style project files: ``*.csproj``, ``*.fsproj``, ``*.vbproj``
* Central Package Management: ``Directory.Packages.props``
* Legacy: ``packages.config``
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from app.services.dependency_parser import ParsedRequirement, RequirementKind

MAX_MANIFEST_BYTES = 256 * 1024
MAX_XML_DEPTH = 64
MAX_PACKAGE_ELEMENTS = 2000

PROJECT_SUFFIXES = (".csproj", ".fsproj", ".vbproj")
PACKAGES_CONFIG = "packages.config"
CENTRAL_PACKAGES = "directory.packages.props"
_IGNORED_PACKAGES = frozenset(
    {
        "microsoft.netcore.app",
        "microsoft.aspnetcore.app",
        "netstandard.library",
    }
)
_EXACT_VERSION_RE = re.compile(
    r"^v?(\d+(?:\.\d+){0,3}(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)$"
)


@dataclass(frozen=True, slots=True)
class DotnetPackage:
    """One declared .NET package reference.

    The shape mirrors the Sprint 57 contract:
    ``{name, version, is_dev, project_file}`` plus parser metadata.
    """

    name: str
    version: str | None
    is_dev: bool
    project_file: str
    kind: RequirementKind
    manifest_line: int | None = None
    manifest_section: str | None = None


@dataclass(slots=True)
class DotnetParseResult:
    """Parsed packages for one project plus an optional parse error."""

    packages: list[DotnetPackage] = field(default_factory=list)
    manifest_found: bool = True
    error: str | None = None
    central_packages_file: str | None = None


def normalize_dotnet_name(name: str) -> str:
    """NuGet package ids are case-insensitive; keep the display name intact."""
    return name.strip()


def is_dotnet_project(path: Path) -> bool:
    """Return ``True`` for SDK-style project files."""
    return path.suffix.lower() in PROJECT_SUFFIXES


def is_dotnet_manifest(path: Path) -> bool:
    """Return ``True`` for a project file or legacy packages.config."""
    return is_dotnet_project(path) or path.name.lower() == PACKAGES_CONFIG


def find_central_packages_file(
    project_path: Path, repo_root: Path
) -> Path | None:
    """Find the nearest ``Directory.Packages.props`` up to the repo root."""
    root = repo_root.resolve()
    current = project_path.resolve().parent
    while True:
        candidate = current / "Directory.Packages.props"
        if candidate.is_file():
            try:
                candidate.resolve().relative_to(root)
            except ValueError:
                return None
            return candidate
        if current == root or current.parent == current:
            return None
        try:
            current.relative_to(root)
        except ValueError:
            return None
        current = current.parent


def parse_dotnet_manifest(
    repo_path: Path,
    *,
    manifest_path: Path,
    central_packages_path: Path | None = None,
) -> DotnetParseResult:
    """Parse one .NET project/config without evaluating MSBuild."""
    root = repo_path.resolve()
    manifest = manifest_path.resolve()
    if not _is_inside(manifest, root) or not manifest.is_file():
        return DotnetParseResult(packages=[], manifest_found=False)

    if manifest.name.lower() == PACKAGES_CONFIG:
        return _parse_packages_config(root, manifest)

    central = central_packages_path or find_central_packages_file(manifest, root)
    central_versions: dict[str, _CentralVersion] = {}
    central_rel: str | None = None
    central_error: str | None = None
    if central is not None:
        parsed_central = parse_central_packages(root, central)
        central_versions = parsed_central.versions
        central_rel = _display_path(root, central)
        central_error = parsed_central.error

    result = _parse_project(root, manifest, central_versions)
    result.central_packages_file = central_rel
    if central_error is not None:
        result.error = central_error
    return result


@dataclass(frozen=True, slots=True)
class _CentralVersion:
    version: str | None
    line: int | None


@dataclass(slots=True)
class _CentralParseResult:
    versions: dict[str, _CentralVersion] = field(default_factory=dict)
    error: str | None = None


def parse_central_packages(
    repo_root: Path, manifest_path: Path
) -> _CentralParseResult:
    """Parse ``Directory.Packages.props`` into a case-insensitive version map."""
    root = repo_root.resolve()
    manifest = manifest_path.resolve()
    if not _is_inside(manifest, root) or not manifest.is_file():
        return _CentralParseResult(error=f"{manifest.name}: not found")

    text, error = _read_xml_text(manifest)
    if text is None:
        return _CentralParseResult(error=f"{_display_path(root, manifest)}: {error}")
    root_element = _parse_xml(text)
    if isinstance(root_element, str):
        return _CentralParseResult(
            error=f"{_display_path(root, manifest)}: {root_element}"
        )

    versions: dict[str, _CentralVersion] = {}
    count = 0
    for element, conditional in _walk_with_conditions(root_element):
        if _local_name(element.tag) not in {"PackageVersion"}:
            continue
        count += 1
        if count > MAX_PACKAGE_ELEMENTS:
            return _CentralParseResult(
                versions=versions,
                error=f"{_display_path(root, manifest)}: too_many_elements",
            )
        name = _attr(element, "Include")
        if not name:
            continue
        raw_version = _attr(element, "Version") or _attr(element, "VersionOverride")
        version, _ = _classify_version(raw_version, conditional=conditional)
        versions[name.lower()] = _CentralVersion(
            version=version,
            line=None,
        )
    return _CentralParseResult(versions=versions)


def _parse_project(
    root: Path,
    manifest: Path,
    central_versions: dict[str, _CentralVersion],
) -> DotnetParseResult:
    text, error = _read_xml_text(manifest)
    if text is None:
        return DotnetParseResult(error=f"{_display_path(root, manifest)}: {error}")
    root_element = _parse_xml(text)
    if isinstance(root_element, str):
        return DotnetParseResult(
            error=f"{_display_path(root, manifest)}: {root_element}"
        )

    manifest_rel = _display_path(root, manifest)
    lines = text.splitlines()
    packages: list[DotnetPackage] = []
    count = 0
    for element, conditional in _walk_with_conditions(root_element):
        if _local_name(element.tag) != "PackageReference":
            continue
        count += 1
        if count > MAX_PACKAGE_ELEMENTS:
            return DotnetParseResult(
                packages=packages,
                error=f"{manifest_rel}: too_many_elements",
            )
        name = _attr(element, "Include")
        if not name or name.lower() in _IGNORED_PACKAGES:
            continue
        inline = _attr(element, "VersionOverride") or _attr(element, "Version")
        central = central_versions.get(name.lower())
        raw_version = inline
        section = "PackageReference"
        if not raw_version and central is not None:
            raw_version = central.version
            section = "PackageVersion"
        version, kind = _classify_version(raw_version, conditional=conditional)
        private_assets = (_attr(element, "PrivateAssets") or "").lower()
        is_dev = "all" in {
            part.strip() for part in private_assets.split(";") if part.strip()
        }
        packages.append(
            DotnetPackage(
                name=normalize_dotnet_name(name),
                version=version,
                is_dev=is_dev,
                project_file=manifest_rel,
                kind=kind,
                manifest_line=_find_project_line(lines, name),
                manifest_section=section,
            )
        )
    return DotnetParseResult(packages=packages)


def _parse_packages_config(root: Path, manifest: Path) -> DotnetParseResult:
    text, error = _read_xml_text(manifest)
    if text is None:
        return DotnetParseResult(error=f"{_display_path(root, manifest)}: {error}")
    root_element = _parse_xml(text)
    if isinstance(root_element, str):
        return DotnetParseResult(
            error=f"{_display_path(root, manifest)}: {error}"
        )

    manifest_rel = _display_path(root, manifest)
    lines = text.splitlines()
    packages: list[DotnetPackage] = []
    count = 0
    for element in root_element.iter():
        if _local_name(element.tag) != "package":
            continue
        count += 1
        if count > MAX_PACKAGE_ELEMENTS:
            return DotnetParseResult(
                packages=packages,
                error=f"{manifest_rel}: too_many_elements",
            )
        name = _attr(element, "id")
        if not name or name.lower() in _IGNORED_PACKAGES:
            continue
        raw_version = _attr(element, "version")
        version, kind = _classify_version(raw_version, conditional=False)
        is_dev = (_attr(element, "developmentDependency") or "").lower() == "true"
        packages.append(
            DotnetPackage(
                name=normalize_dotnet_name(name),
                version=version,
                is_dev=is_dev,
                project_file=manifest_rel,
                kind=kind,
                manifest_line=_find_packages_config_line(lines, name),
                manifest_section="packages.config",
            )
        )
    return DotnetParseResult(packages=packages)


def to_requirement(package: DotnetPackage) -> ParsedRequirement:
    """Convert a .NET package to the shared dependency model."""
    return ParsedRequirement(
        name=package.name,
        declared=package.version or "(unresolved)",
        kind=package.kind,
        current=package.version,
        manifest_line=package.manifest_line,
        manifest_section=package.manifest_section,
        manifest_path=package.project_file,
        is_dev=package.is_dev,
    )


def _walk_with_conditions(
    element: ET.Element, inherited: bool = False
) -> list[tuple[ET.Element, bool]]:
    """Return elements with a flag telling whether MSBuild must evaluate them."""
    local = _local_name(element.tag)
    conditional = inherited or local in {"Choose", "When", "Otherwise"}
    conditional = conditional or _attr(element, "Condition") is not None
    result: list[tuple[ET.Element, bool]] = [(element, conditional)]
    for child in list(element):
        result.extend(_walk_with_conditions(child, conditional))
    return result


def _classify_version(
    raw: str | None, *, conditional: bool
) -> tuple[str | None, RequirementKind]:
    if conditional:
        return None, "range"
    value = (raw or "").strip()
    if not value or "$(" in value or "@(" in value:
        return None, "range"
    if value in {"*", "latest"}:
        return None, "range"

    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if "," not in inner:
            return inner or None, "exact"
        lower = inner.split(",", 1)[0].strip()
        return lower or None, "range"
    if value[0] in "[(" and value[-1] in "])":
        inner = value[1:-1].strip()
        if "," not in inner:
            return inner.strip("[]() ") or None, "exact"
        lower = inner.split(",", 1)[0].strip()
        return lower or None, "range"
    if "*" in value:
        lower = value.split("*", 1)[0].rstrip(".")
        return lower or None, "range"

    exact = _EXACT_VERSION_RE.match(value)
    if exact is not None:
        return exact.group(1), "exact"
    return None, "range"


def _read_xml_text(path: Path) -> tuple[str | None, str | None]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, str(exc)
    if size > MAX_MANIFEST_BYTES:
        return None, "manifest_too_large"
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, str(exc)
    if b"\x00" in raw:
        return None, "binary_manifest"
    text = raw.decode("utf-8", errors="replace")
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        return None, "dtd_forbidden"
    return text, None


def _parse_xml(text: str) -> ET.Element | str:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return f"invalid_xml: {exc}"
    depth = _depth(root)
    if depth > MAX_XML_DEPTH:
        return "xml_too_deep"
    return root


def _depth(element: ET.Element, level: int = 1) -> int:
    children = list(element)
    if not children:
        return level
    return max(_depth(child, level + 1) for child in children)


def _local_name(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _attr(element: ET.Element, name: str) -> str | None:
    for key, value in element.attrib.items():
        if _local_name(key).lower() == name.lower():
            return value
    return None


def _find_project_line(lines: list[str], name: str) -> int | None:
    needle = f'Include="{name}"'
    single_quote = f"Include='{name}'"
    for index, line in enumerate(lines):
        if "<PackageReference" in line and (
            needle in line or single_quote in line
        ):
            return index + 1
    return None


def _find_packages_config_line(lines: list[str], name: str) -> int | None:
    needle = f'id="{name}"'
    single_quote = f"id='{name}'"
    for index, line in enumerate(lines):
        if "<package" in line and (needle in line or single_quote in line):
            return index + 1
    return None


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


__all__ = [
    "CENTRAL_PACKAGES",
    "PACKAGES_CONFIG",
    "PROJECT_SUFFIXES",
    "DotnetPackage",
    "DotnetParseResult",
    "find_central_packages_file",
    "is_dotnet_manifest",
    "is_dotnet_project",
    "normalize_dotnet_name",
    "parse_central_packages",
    "parse_dotnet_manifest",
    "to_requirement",
]
