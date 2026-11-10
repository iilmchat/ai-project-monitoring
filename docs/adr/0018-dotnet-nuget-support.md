# ADR-0018: .NET manifests & NuGet client

**Статус:** Accepted
**Дата:** 2026-11-11
**Контекст:** Спринт 57 (S57-001..S57-005), v1.3.0; KI-025

## Контекст

Нужно проверять устаревшие зависимости, CVE и обновлять пакеты в
C#/.NET-проектах, не запуская сборку и не изменяя репозиторий при проверке.
.NET описывает зависимости несколькими способами: SDK-style `.csproj`
(`PackageReference`), Central Package Management
(`Directory.Packages.props` + `PackageVersion`/`VersionOverride`), legacy
`packages.config`. Версии могут задаваться MSBuild-свойствами и условиями,
которые невозможно вычислить без MSBuild.

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| Запускать `dotnet restore`/MSBuild и читать `project.assets.json` | Точные транзитивные версии | Мутирует `obj/`, требует SDK и сети, нарушает read-only-проверку |
| Собственный XML-парсер + NuGet flat container | Read-only, без SDK, работает офлайн для уже закэшированных версий | Не раскрывает MSBuild-свойства/conditions, транзитивные зависимости |
| Только `dotnet list package --outdated` | Просто | Требует SDK/restore и не даёт отчёт без CLI |
| Сторонняя библиотека (`defusedxml`, NuGet.Client) | Меньше кода | Новая зависимость и ADR; избыточно для 3 форматов |

## Решение

- Собственный парсер `app/services/dotnet_parser.py` на stdlib
  `xml.etree.ElementTree`. DTD/`<!ENTITY>` отвергаются до разбора, лимиты:
  256 KiB, глубина 64, 2000 пакетов на файл. Namespace MSBuild снимается.
- Приоритет версии: `VersionOverride` → `Version` → ближайший
  `Directory.Packages.props` (`PackageVersion`) → `packages.config`.
  `PrivateAssets="all"` / `developmentDependency="true"` → `is_dev`.
- `$(Property)`, `Condition`, `Choose/When`, `Import` не вычисляются: пакет
  получает `status=unknown`, причина — в `ecosystem.error` и UI (KI-025).
- `app/providers/nuget_client.py` повторяет контракт
  `PyPIClient`/`NpmClient`: `get_latest_version()`, flat container
  `index.json`, lower-case id, stable SemVer, timeout/backoff/404 и общий
  `dependency_cache` (`nuget:<lower-id>`).
- CVE — OSV `ecosystem="NuGet"`; обновление — только §17
  (`dotnet list --outdated --no-restore`, затем
  `dotnet add --no-restore`), с `confirm=true`, чистым worktree и аудитом.

## Последствия

- Проверка зависимостей и CVE работает без .NET SDK и не меняет репозиторий.
- Часть версий честно помечается `unknown`; это документировано в KI-025.
- Приватные NuGet-фиды, `NuGet.config` credentials, MSBuild-evaluation и
  транзитивные зависимости остаются вне scope v1.3.0.
- Обновление пакетов требует установленного `dotnet` CLI; при его отсутствии
  возвращается `409 dotnet_unavailable`.
- При появлении требования к точным транзитивным версиям решение нужно
  пересмотреть (кандидат — чтение `project.assets.json` read-only).
