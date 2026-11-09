"""Security tests: OSV parsing, secret scanning, cache and API (S28)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import httpx
from app.models.entities import Repository
from app.providers.osv_client import (
    OsvClient,
    OsvQuery,
    OsvQueryResult,
    OsvVulnerability,
    parse_cvss_score,
    parse_vulnerability,
    severity_from_score,
)
from app.services.secret_scanner import mask_secret, scan_secrets
from app.services.security_service import SecurityService
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

AWS_KEY = "AKIAABCDEFGHIJKLMNOP"
GITHUB_TOKEN = "ghp_" + "A" * 32 + "6789"
JWT = (
    "eyJhbGciOiJIUzI1NiJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
    "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
)


class FakeOsv:
    """Deterministic OSV substitute."""

    def __init__(
        self,
        vulns: tuple[OsvVulnerability, ...] = (),
        *,
        status: str = "ok",
        error: str | None = None,
    ) -> None:
        self.vulns = vulns
        self.status = status
        self.error = error
        self.calls: list[list[OsvQuery]] = []

    async def query_batch(
        self, queries: Sequence[OsvQuery]
    ) -> list[OsvQueryResult]:
        self.calls.append(list(queries))
        if self.status != "ok":
            return [
                OsvQueryResult(status=self.status, error=self.error)  # type: ignore[arg-type]
                for _ in queries
            ]
        return [OsvQueryResult(vulns=self.vulns) for _ in queries]


def _vulnerability(
    *,
    osv_id: str = "GHSA-9wx4-h78v-vm56",
    severity: str = "high",
    cvss_score: float | None = 7.5,
) -> OsvVulnerability:
    return OsvVulnerability(
        osv_id=osv_id,
        summary="Credentials could be sent to a different host",
        severity=severity,  # type: ignore[arg-type]
        cvss_score=cvss_score,
        aliases=("CVE-2018-18074",),
        fixed_version="2.20.0",
        references=("https://github.com/advisories/GHSA-9wx4-h78v-vm56",),
    )


def _write_requirements(path: Path, content: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "requirements.txt").write_text(content, encoding="utf-8")
    return path


def test_cvss_vector_is_parsed_and_mapped_to_severity() -> None:
    score = parse_cvss_score(
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    )

    assert score == 9.8
    assert severity_from_score(score) == "critical"
    assert severity_from_score(7.5) == "high"
    assert severity_from_score(5.0) == "medium"
    assert severity_from_score(2.0) == "low"
    assert severity_from_score(None) == "unknown"


def test_parse_vulnerability_extracts_aliases_and_min_fixed_version() -> None:
    raw = {
        "id": "GHSA-9wx4-h78v-vm56",
        "summary": "Credentials leak",
        "aliases": ["CVE-2018-18074", "GHSA-other"],
        "severity": [
            {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}
        ],
        "affected": [
            {
                "ranges": [
                    {
                        "type": "ECOSYSTEM",
                        "events": [
                            {"introduced": "0"},
                            {"fixed": "2.20.0"},
                            {"fixed": "2.19.1"},
                        ],
                    }
                ]
            }
        ],
        "references": [{"url": "https://osv.dev/GHSA-9wx4-h78v-vm56"}],
    }

    parsed = parse_vulnerability(raw)

    assert parsed is not None
    assert parsed.osv_id == "GHSA-9wx4-h78v-vm56"
    assert parsed.severity == "critical"
    assert parsed.cvss_score == 9.8
    assert parsed.cve_ids == ("CVE-2018-18074",)
    assert parsed.fixed_version == "2.19.1"
    assert parsed.references == ("https://osv.dev/GHSA-9wx4-h78v-vm56",)


def test_parse_vulnerability_falls_back_to_database_severity() -> None:
    parsed = parse_vulnerability(
        {
            "id": "OSV-1",
            "summary": "Example",
            "database_specific": {"severity": "MODERATE"},
        }
    )

    assert parsed is not None
    assert parsed.severity == "medium"
    assert parsed.cvss_score is None


async def test_osv_client_parses_querybatch_response() -> None:
    payload = {
        "results": [
            {
                "vulns": [
                    {
                        "id": "GHSA-9wx4-h78v-vm56",
                        "summary": "Credentials leak",
                        "aliases": ["CVE-2018-18074"],
                        "severity": [
                            {
                                "type": "CVSS_V3",
                                "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
                            }
                        ],
                        "affected": [
                            {
                                "ranges": [
                                    {
                                        "type": "ECOSYSTEM",
                                        "events": [{"fixed": "2.20.0"}],
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/querybatch"
        body = json.loads(request.content)
        assert body["queries"][0]["package"]["ecosystem"] == "PyPI"
        return httpx.Response(200, json=payload)

    client = OsvClient(
        transport=httpx.MockTransport(handler),
        max_attempts=1,
    )

    results = await client.query_batch(
        [OsvQuery(package="requests", version="2.19.0", ecosystem="PyPI")]
    )

    assert len(results) == 1
    assert results[0].status == "ok"
    assert results[0].vulns[0].cve_ids == ("CVE-2018-18074",)
    assert results[0].vulns[0].fixed_version == "2.20.0"


async def test_osv_client_degrades_on_server_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = OsvClient(
        transport=httpx.MockTransport(handler),
        max_attempts=1,
    )

    results = await client.query_batch(
        [OsvQuery(package="requests", version="2.19.0", ecosystem="PyPI")]
    )

    assert results[0].status == "unavailable"
    assert results[0].error == "osv_unavailable"


def test_secret_scanner_finds_masks_and_ignores(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.py").write_text(
        "\n".join(
            [
                f"AWS_KEY = '{AWS_KEY}'",
                "AWS_SECRET_ACCESS_KEY = '" + "A" * 40 + "'",
                f"TOKEN = '{GITHUB_TOKEN}'",
                f"JWT = '{JWT}'",
                "-----BEGIN RSA PRIVATE KEY-----",
                f"IGNORED = '{AWS_KEY}'  # iiruchating:ignore-secret",
            ]
        ),
        encoding="utf-8",
    )
    ignored_dir = repo / "node_modules"
    ignored_dir.mkdir()
    (ignored_dir / "bad.py").write_text(f"KEY='{AWS_KEY}'", encoding="utf-8")
    (repo / "binary.bin").write_bytes(b"\x00\x01" + AWS_KEY.encode())

    report = scan_secrets(str(repo))

    assert report.status == "ok"
    types = {finding.type for finding in report.findings}
    assert types == {
        "aws_access_key",
        "aws_secret_key",
        "github_token",
        "jwt",
        "private_key",
    }
    assert all(finding.file != "node_modules/bad.py" for finding in report.findings)
    serialized = report.model_dump_json()
    assert AWS_KEY not in serialized
    assert GITHUB_TOKEN not in serialized
    first = next(item for item in report.findings if item.type == "github_token")
    assert first.preview.startswith("ghp_")
    assert "****" in first.preview


def test_secret_scanner_limits_size_and_marks_partial(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "big.txt").write_text(f"KEY={AWS_KEY}", encoding="utf-8")

    report = scan_secrets(str(repo), max_file_bytes=4)

    assert report.status == "partial"
    assert report.findings == []


def test_mask_secret_never_returns_full_value() -> None:
    assert mask_secret("short") == "****"
    assert mask_secret(GITHUB_TOKEN) == "ghp_****6789"
    assert GITHUB_TOKEN not in mask_secret(GITHUB_TOKEN)


async def test_service_reports_cve_and_caches(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(
        tmp_path / "repo",
        "requests==2.19.0\nflask>=2.0\n",
    )
    osv = FakeOsv((_vulnerability(),))
    service = SecurityService(session_factory, osv)

    report = await service.get_report(1, str(repo))

    assert report.status == "ok"
    python = report.ecosystems[0]
    assert python.status == "ok"
    assert python.total_packages == 2
    assert python.packages_checked == 2
    assert len(python.vulnerabilities) == 2
    assert python.vulnerabilities[0].package == "flask"
    assert python.vulnerabilities[0].version_source == "lower_bound"
    assert python.vulnerabilities[1].package == "requests"
    assert python.vulnerabilities[1].version_source == "exact"
    assert python.vulnerabilities[1].cve_ids == ["CVE-2018-18074"]
    assert report.summary.vulnerable == 2
    assert report.summary.high == 2

    osv.calls.clear()
    cached = await service.get_report(1, str(repo))

    assert cached.ecosystems[0].packages_checked == 2
    assert osv.calls == []

    refreshed = await service.get_report(1, str(repo), refresh=True)

    assert refreshed.ecosystems[0].packages_checked == 2
    assert len(osv.calls) == 1


async def test_service_filters_min_severity_but_keeps_summary(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(tmp_path / "repo", "requests==2.19.0\n")
    osv = FakeOsv(
        (
            _vulnerability(osv_id="GHSA-high", severity="high", cvss_score=7.5),
            _vulnerability(osv_id="GHSA-medium", severity="medium", cvss_score=5.0),
        )
    )
    service = SecurityService(session_factory, osv)

    default = await service.get_report(1, str(repo), min_severity="high")
    full = await service.get_report(1, str(repo), min_severity="all")

    assert [item.osv_id for item in default.ecosystems[0].vulnerabilities] == [
        "GHSA-high"
    ]
    assert default.summary.medium == 1
    assert len(full.ecosystems[0].vulnerabilities) == 2


async def test_service_marks_unavailable_without_cache(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(tmp_path / "repo", "requests==2.19.0\n")
    service = SecurityService(
        session_factory,
        FakeOsv(status="unavailable", error="osv_unavailable"),
    )

    report = await service.get_report(1, str(repo))

    assert report.status == "unavailable"
    assert report.ecosystems[0].status == "unavailable"
    assert report.ecosystems[0].packages_checked == 0
    assert report.ecosystems[0].total_packages == 1
    assert report.error == "osv_unavailable"


async def test_service_uses_stale_cache_on_osv_error(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(tmp_path / "repo", "requests==2.19.0\n")
    osv = FakeOsv((_vulnerability(),))
    service = SecurityService(session_factory, osv)
    await service.get_report(1, str(repo))

    osv.status = "rate_limited"
    osv.error = "rate_limited"
    report = await service.get_report(1, str(repo), refresh=True)

    assert report.ecosystems[0].status == "ok"
    assert report.ecosystems[0].vulnerabilities[0].osv_id == "GHSA-9wx4-h78v-vm56"
    assert report.ecosystems[0].error == "rate_limited"


async def test_service_handles_node_manifest_and_secret_opt_out(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = tmp_path / "node"
    repo.mkdir()
    (repo / "package.json").write_text(
        '{"dependencies": {"react": "^19.0.0", "local": "file:../local"}}',
        encoding="utf-8",
    )
    (repo / "leak.txt").write_text(f"KEY={AWS_KEY}", encoding="utf-8")
    osv = FakeOsv((_vulnerability(osv_id="GHSA-react", severity="critical"),))
    service = SecurityService(session_factory, osv)

    report = await service.get_report(
        1, str(repo), include_secrets=False, min_severity="all"
    )

    node = report.ecosystems[1]
    assert node.ecosystem == "node"
    assert node.total_packages == 1
    assert node.vulnerabilities[0].version_source == "lower_bound"
    assert report.secrets.status == "skipped"
    assert report.summary.secrets_found == 0


async def test_service_unknown_packages_are_not_clean(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(tmp_path / "repo", "some-lib\n")
    service = SecurityService(session_factory, FakeOsv())

    report = await service.get_report(1, str(repo))

    python = report.ecosystems[0]
    assert python.total_packages == 1
    assert python.packages_checked == 0
    assert python.unknown_packages[0].reason == "unresolved_range"
    assert report.summary.unknown == 1


async def test_security_api(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repo = _write_requirements(tmp_path / "repo", "requests==2.19.0\n")
    async with session_factory() as session:
        repository = Repository(path=str(repo.resolve()), tracked=True)
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        repository_id = repository.id
    app.state.security_service = SecurityService(
        session_factory,
        FakeOsv((_vulnerability(),)),
    )

    response = await client.get(
        f"/api/v1/repositories/{repository_id}/security",
        params={"include_secrets": False, "min_severity": "all"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository_id"] == repository_id
    assert payload["status"] == "ok"
    assert payload["summary"]["high"] == 1
    assert payload["ecosystems"][0]["vulnerabilities"][0]["osv_id"].startswith(
        "GHSA-"
    )
    assert payload["secrets"]["status"] == "skipped"


async def test_security_api_missing_repository(client: AsyncClient) -> None:
    response = await client.get("/api/v1/repositories/999999/security")

    assert response.status_code == 404
