"""Sprint 57: .NET parser, NuGet client and service integration tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import httpx
import pytest
from app.providers.nuget_client import NuGetClient
from app.providers.osv_client import OsvQuery, OsvQueryResult, OsvVulnerability
from app.providers.package_versions import PackageVersionResult
from app.services.dependency_service import DependencyService
from app.services.dotnet_parser import (
    parse_central_packages,
    parse_dotnet_manifest,
)
from app.services.manifest_discovery import (
    discover_manifests,
    parse_dotnet_manifests,
)
from app.services.security_service import SecurityService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_parser_handles_inline_versions_dev_and_ignored_items(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    project = _write(
        repo / "src" / "Demo.csproj",
        """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
    <PackageReference Include="xunit" Version="2.9.2" PrivateAssets="all" />
    <PackageReference Include="Floating.Pkg" Version="1.*" />
    <PackageReference Include="Property.Pkg" Version="$(SomeVersion)" />
    <PackageReference Include="Conditional.Pkg" Version="1.0.0"
                      Condition="'$(TargetFramework)' == 'net8.0'" />
    <ProjectReference Include="../Other/Other.csproj" />
    <FrameworkReference Include="Microsoft.AspNetCore.App" />
    <PackageReference Include="Microsoft.NETCore.App" Version="8.0.0" />
  </ItemGroup>
</Project>""",
    )

    result = parse_dotnet_manifest(repo, manifest_path=project)

    assert result.error is None
    by_name = {item.name: item for item in result.packages}
    assert set(by_name) == {
        "Newtonsoft.Json",
        "xunit",
        "Floating.Pkg",
        "Property.Pkg",
        "Conditional.Pkg",
    }
    assert by_name["Newtonsoft.Json"].kind == "exact"
    assert by_name["Newtonsoft.Json"].version == "13.0.3"
    assert by_name["Newtonsoft.Json"].project_file == "src/Demo.csproj"
    assert by_name["xunit"].is_dev is True
    assert by_name["Floating.Pkg"].kind == "range"
    assert by_name["Floating.Pkg"].version == "1"
    assert by_name["Property.Pkg"].version is None
    assert by_name["Property.Pkg"].kind == "range"
    assert by_name["Conditional.Pkg"].version is None
    assert by_name["Newtonsoft.Json"].manifest_line is not None


def test_central_package_management_and_version_override(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / "Directory.Packages.props",
        """<Project>
  <ItemGroup>
    <PackageVersion Include="Serilog" Version="3.1.1" />
    <PackageVersion Include="CentralOnly" Version="[2.0.0]" />
  </ItemGroup>
</Project>""",
    )
    project = _write(
        repo / "App" / "App.csproj",
        """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="Serilog" VersionOverride="4.0.0" />
    <PackageReference Include="CentralOnly" />
    <PackageReference Include="MissingCentral" />
  </ItemGroup>
</Project>""",
    )

    result = parse_dotnet_manifest(repo, manifest_path=project)

    by_name = {item.name: item for item in result.packages}
    assert result.central_packages_file == "Directory.Packages.props"
    assert by_name["Serilog"].version == "4.0.0"
    assert by_name["Serilog"].kind == "exact"
    assert by_name["CentralOnly"].version == "2.0.0"
    assert by_name["CentralOnly"].kind == "exact"
    assert by_name["CentralOnly"].manifest_section == "PackageVersion"
    assert by_name["MissingCentral"].version is None
    assert by_name["MissingCentral"].kind == "range"


def test_nearest_directory_packages_props_wins(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / "Directory.Packages.props",
        '<Project><ItemGroup><PackageVersion Include="Pkg" Version="1.0.0" />'
        "</ItemGroup></Project>",
    )
    nested_props = _write(
        repo / "src" / "Directory.Packages.props",
        '<Project><ItemGroup><PackageVersion Include="Pkg" Version="2.0.0" />'
        "</ItemGroup></Project>",
    )
    project = _write(
        repo / "src" / "App" / "App.csproj",
        '<Project><ItemGroup><PackageReference Include="Pkg" />'
        "</ItemGroup></Project>",
    )

    assert parse_central_packages(repo, nested_props).versions["pkg"].version == "2.0.0"
    result = parse_dotnet_manifest(repo, manifest_path=project)

    assert result.packages[0].version == "2.0.0"
    assert result.central_packages_file == "src/Directory.Packages.props"


def test_packages_config_legacy_and_dev_flag(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    manifest = _write(
        repo / "Legacy" / "packages.config",
        """<?xml version="1.0" encoding="utf-8"?>
<packages>
  <package id="Newtonsoft.Json" version="12.0.3" targetFramework="net48" />
  <package id="StyleCop.Analyzers" version="1.2.0-beta.507"
           developmentDependency="true" targetFramework="net48" />
</packages>""",
    )

    result = parse_dotnet_manifest(repo, manifest_path=manifest)

    by_name = {item.name: item for item in result.packages}
    assert by_name["Newtonsoft.Json"].version == "12.0.3"
    assert by_name["Newtonsoft.Json"].manifest_section == "packages.config"
    assert by_name["StyleCop.Analyzers"].is_dev is True
    assert by_name["StyleCop.Analyzers"].kind == "exact"


def test_parser_rejects_dtd_and_broken_xml(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    dtd = _write(
        repo / "Evil.csproj",
        """<?xml version="1.0"?>
<!DOCTYPE project [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<Project><ItemGroup><PackageReference Include="&xxe;" Version="1.0" />
</ItemGroup></Project>""",
    )
    broken = _write(repo / "Broken.csproj", "<Project><ItemGroup>")

    dtd_result = parse_dotnet_manifest(repo, manifest_path=dtd)
    broken_result = parse_dotnet_manifest(repo, manifest_path=broken)

    assert dtd_result.packages == []
    assert dtd_result.error is not None
    assert "dtd_forbidden" in dtd_result.error
    assert broken_result.error is not None
    assert "invalid_xml" in broken_result.error


def test_multi_targeting_does_not_duplicate_packages(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    project = _write(
        repo / "Multi.csproj",
        """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFrameworks>net8.0;net48</TargetFrameworks>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Serilog" Version="3.1.1" />
  </ItemGroup>
</Project>""",
    )

    result = parse_dotnet_manifest(repo, manifest_path=project)

    assert [item.name for item in result.packages] == ["Serilog"]
    assert result.packages[0].version == "3.1.1"


def test_broken_central_file_keeps_inline_project_versions(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / "Directory.Packages.props",
        '<Project><ItemGroup><PackageVersion Include="Inline" Version="2.0.0" />',
    )
    project = _write(
        repo / "Demo.csproj",
        '<Project><ItemGroup><PackageReference Include="Inline" Version="1.0.0" />'
        "</ItemGroup></Project>",
    )

    result = parse_dotnet_manifest(repo, manifest_path=project)

    assert result.error is not None
    assert result.packages[0].name == "Inline"
    assert result.packages[0].version == "1.0.0"


def test_discovery_finds_dotnet_projects_and_ignores_obj(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "App.csproj", "<Project />")
    _write(repo / "src" / "Lib.fsproj", "<Project />")
    _write(repo / "obj" / "Generated.csproj", "<Project />")
    _write(repo / "bin" / "Ignored.vbproj", "<Project />")

    discovered = discover_manifests(repo)

    assert {
        path.relative_to(repo).as_posix() for path in discovered.dotnet
    } == {"App.csproj", "src/Lib.fsproj"}
    assert parse_dotnet_manifests(discovered).manifest_found is True


async def test_nuget_client_picks_latest_stable_and_lowercases_id() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(
            200,
            json={"versions": ["1.2.0", "1.10.0", "2.0.0-beta.1", "1.9.9"]},
        )

    client = NuGetClient(
        transport=httpx.MockTransport(handler),
        max_attempts=1,
    )
    result = await client.get_latest_version("Newtonsoft.Json")

    assert result.latest == "1.10.0"
    assert result.status == "ok"
    assert requested == ["/v3-flatcontainer/newtonsoft.json/index.json"]


async def test_nuget_client_handles_prerelease_only_and_404() -> None:
    def prerelease_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"versions": ["2.0.0-rc.1"]})

    def not_found_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    prerelease = await NuGetClient(
        transport=httpx.MockTransport(prerelease_handler), max_attempts=1
    ).get_latest_version("pkg")
    missing = await NuGetClient(
        transport=httpx.MockTransport(not_found_handler), max_attempts=1
    ).get_latest_version("pkg")

    assert prerelease.latest is None
    assert prerelease.status == "not_found"
    assert missing.latest is None
    assert missing.status == "not_found"


async def test_nuget_client_degrades_on_server_error_and_timeout() -> None:
    def server_error(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom", request=request)

    unavailable = await NuGetClient(
        transport=httpx.MockTransport(server_error), max_attempts=1
    ).get_latest_version("pkg")
    timed_out = await NuGetClient(
        transport=httpx.MockTransport(timeout), max_attempts=1
    ).get_latest_version("pkg")

    assert unavailable.status == "unavailable"
    assert unavailable.error == "registry_unavailable"
    assert timed_out.status == "timeout"
    assert timed_out.error == "timeout"


class FakeRegistry:
    def __init__(self, versions: dict[str, str | None]) -> None:
        self.versions = versions
        self.calls: list[str] = []

    async def get_latest_version(self, package: str) -> PackageVersionResult:
        self.calls.append(package)
        latest = self.versions.get(package)
        if latest is None:
            return PackageVersionResult(latest=None, status="not_found")
        return PackageVersionResult(latest=latest, status="ok")


async def test_dependency_service_dotnet_report_and_cache(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / "Demo.csproj",
        """<Project><ItemGroup>
  <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
  <PackageReference Include="Serilog" Version="3.0.0" />
</ItemGroup></Project>""",
    )
    nuget = FakeRegistry({"Newtonsoft.Json": "13.0.4", "Serilog": "3.0.0"})
    service = DependencyService(
        session_factory,
        FakeRegistry({}),
        FakeRegistry({}),
        nuget,
    )

    report = await service.get_report(1, str(repo), ecosystem="dotnet")

    ecosystem = report.ecosystems[0]
    assert ecosystem.ecosystem == "dotnet"
    assert ecosystem.status == "ok"
    assert ecosystem.outdated == 1
    assert ecosystem.up_to_date == 1
    by_name = {item.name: item for item in ecosystem.packages}
    assert by_name["Newtonsoft.Json"].severity == "patch"

    nuget.calls.clear()
    cached = await service.get_report(1, str(repo), ecosystem="dotnet")
    assert cached.ecosystems[0].source == "cache"
    assert nuget.calls == []


async def test_combined_report_includes_dotnet(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(repo / "requirements.txt", "fastapi==0.115.6\n")
    _write(repo / "package.json", '{"dependencies": {"react": "^19.0.0"}}')
    _write(
        repo / "Demo.csproj",
        '<Project><ItemGroup><PackageReference Include="Serilog" Version="3.0.0" />'
        "</ItemGroup></Project>",
    )
    service = DependencyService(
        session_factory,
        FakeRegistry({"fastapi": "0.115.6"}),
        FakeRegistry({"react": "19.0.0"}),
        FakeRegistry({"Serilog": "3.0.0"}),
    )

    report = await service.get_report(1, str(repo), ecosystem="all")

    assert [item.ecosystem for item in report.ecosystems] == [
        "python",
        "node",
        "dotnet",
    ]


class FakeOsv:
    def __init__(self) -> None:
        self.queries: list[OsvQuery] = []

    async def query_batch(
        self, queries: Sequence[OsvQuery]
    ) -> list[OsvQueryResult]:
        self.queries.extend(queries)
        vuln = OsvVulnerability(
            osv_id="GHSA-test-dotnet",
            summary="Unsafe deserialization",
            severity="high",
            cvss_score=7.5,
            aliases=("CVE-2026-0001",),
            fixed_version="13.0.4",
        )
        return [OsvQueryResult(vulns=(vuln,)) for _ in queries]


async def test_security_service_uses_nuget_osv_ecosystem(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / "Demo.csproj",
        """<Project><ItemGroup>
  <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
</ItemGroup></Project>""",
    )
    osv = FakeOsv()
    service = SecurityService(session_factory, osv)

    report = await service.get_report(1, str(repo), include_secrets=False)

    dotnet = next(item for item in report.ecosystems if item.ecosystem == "dotnet")
    assert dotnet.vulnerabilities[0].cve_ids == ["CVE-2026-0001"]
    assert any(query.ecosystem == "NuGet" for query in osv.queries)
    assert all(
        query.ecosystem != "NuGet" or query.package == "Newtonsoft.Json"
        for query in osv.queries
    )


def test_parser_missing_manifest(tmp_path: Path) -> None:
    result = parse_dotnet_manifest(
        tmp_path, manifest_path=tmp_path / "nope.csproj"
    )

    assert result.manifest_found is False
    assert result.packages == []


def test_parser_rejects_manifest_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = _write(tmp_path / "outside.csproj", "<Project />")

    result = parse_dotnet_manifest(repo, manifest_path=outside)

    assert result.manifest_found is False
    assert result.packages == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.2.3", ("1.2.3", "exact")),
        ("[1.2.3]", ("1.2.3", "exact")),
        ("[1.0,2.0)", ("1.0", "range")),
        ("1.2.*", ("1.2", "range")),
        ("*", (None, "range")),
        ("$(Version)", (None, "range")),
    ],
)
def test_version_classification(
    tmp_path: Path, raw: str, expected: tuple[str | None, str]
) -> None:
    repo = tmp_path / "repo"
    project = _write(
        repo / "Demo.csproj",
        f'<Project><ItemGroup><PackageReference Include="Pkg" '
        f'Version="{raw}" /></ItemGroup></Project>',
    )

    package = parse_dotnet_manifest(repo, manifest_path=project).packages[0]

    assert (package.version, package.kind) == expected
