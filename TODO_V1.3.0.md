# TODO v1.3.0 — .NET, Team Edition & Advanced Security

**Статус:** Sprint 56 — планирование завершено; спринты 57–59 — реализованы;
v1.3.0 выпущен.
**База:** v1.2.0 «AI Analytics & Cross-Platform» (AI review, conflict resolver,
release notes, conversational RAG, матрица Windows/macOS/Linux).
**Цель:** расширить аудит зависимостей на экосистему .NET (NuGet), добавить
роли и журнал аудита для командной работы, а также SAST и генерацию конфигураций
для автоматических PR (Dependabot/Renovate).

**Источники истины:** [`docs/SPEC.md`](docs/SPEC.md),
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md),
[`docs/RULES.md`](docs/RULES.md).

---

## 1. Принципы v1.3.0

- **Read-only по умолчанию.** Аудит зависимостей, CVE, SAST, аудит-лог и
  генерация конфигураций **читают** репозиторий. Единственные мутации —
  существующие Actions (`fetch`/`pull`/`push`/`stash`/`commit`/
  `update-dependencies`) и явное применение сгенерированной конфигурации
  (`automation/apply`), каждое — с `confirm=true`, preflight и аудитом.
- **Никакой самодеятельной сборки.** В режиме проверок не запускаются
  `dotnet restore/build/publish`, `pip install`, `npm install` и не исполняется
  код проверяемого проекта. `dotnet list`/`dotnet add` допускаются только в
  рамках §3.20 с `--no-restore` и явным подтверждением.
- **Честный partial result.** Ошибка одного пакета/манифеста/инструмента не
  скрывает остальные: отчёт остаётся HTTP 200, проблемные записи получают
  `unknown`/`unavailable`/`partial` и понятную причину.
- **Безопасный XML.** `.csproj`/`Directory.Packages.props` парсятся без
  вычисления MSBuild-свойств, без DTD/внешних сущностей, с лимитом размера и
  глубины. Нераскрываемые выражения (`$(...)`, conditions, imports) честно
  помечаются `unknown`, а не угадываются.
- **Роли — серверные.** Роль берётся из БД на каждом запросе и не доверяется
  claim'у JWT. `AUTH_ENABLED=false` — локальный режим с неявным `admin`.
- **Audit trail — append-only.** `audit_log` фиксирует кто/что/когда/результат;
  нет API для изменения или удаления записей; секреты и содержимое файлов не
  пишутся.
- **SAST — только анализ.** `bandit`/`semgrep` запускаются как внешние
  read-only инструменты с таймаутом, лимитом вывода и без сети/фиксов.
- **ADR first.** До реализации фиксируются ADR: .NET-парсинг и NuGet-клиент,
  роли/аудит, SAST-политика, генерация конфигураций автоматических PR.

**Вне scope v1.3.0:** автоматический `git push` и создание PR из приложения,
автоматическое исправление найденных SAST-проблем, полноценный MSBuild-
evaluation, приватные NuGet-фиды и аутентификация в них, SSO/OIDC, тонкая
RBAC-матрица на отдельные репозитории.

---

## 2. Sprint 56 — Planning (S56-001..S56-003)

**Цель:** зафиксировать контракты .NET, командной работы и SAST до написания
кода.

- [x] **S56-001. Roadmap:** `TODO_V1.3.0.md` — спринты 57–59, контракты,
      лимиты, риски, трассировка на SPEC/ARCHITECTURE.
- [x] **S56-002. Документация:** SPEC §3.15 (dotnet), §3.31–§3.33 (роли,
      audit log, SAST, автоматические PR), ARCHITECTURE §29–§32, KI-025,
      анонс v1.3.0 в README.
- [x] **S56-003. DoD и консистентность:** Definition of Done для каждого
      спринта; `NuGetClient` согласован с `PyPIClient`/`NpmClient`; ссылки
      между TODO/SPEC/ARCHITECTURE/KNOWN_ISSUES проверены.

**DoD Sprint 56:**

- [x] `TODO_V1.3.0.md` создан в корне и содержит спринты 57–59 с DoD.
- [x] В SPEC `dotnet` добавлен как поддерживаемая экосистема §3.15 (план),
      описаны роли `Admin`/`Auditor` и Audit Log API.
- [x] ARCHITECTURE описывает `NuGetClient` (XML + NuGet API) и `SastService`
      (bandit/semgrep), а также роли и audit trail.
- [x] KI-025 добавлена; счётчик проблем обновлён.
- [x] README Roadmap содержит анонс v1.3.0 (.NET, Team Edition, SAST).
- [x] Код приложения не менялся (только документация).

---

## 3. Sprint 57 — .NET Ecosystem Support (NuGet) (✅)

**Цель:** довести аудит зависимостей, CVE, обновление и поиск по коду до
C#/.NET-проектов, не запуская MSBuild и не изменяя репозиторий при проверке.

### 3.1. Парсер .NET-манифестов

**Новый модуль:** `backend/app/services/dotnet_parser.py`
(в паре с расширением `ManifestDiscovery`).

**Форматы:**

| Файл | Что читаем | Приоритет |
|------|------------|-----------|
| `*.csproj`, `*.fsproj`, `*.vbproj` | `PackageReference Include` + `Version` / `VersionOverride` | 1 |
| `Directory.Packages.props` | `PackageVersion Include` + `Version` (Central Package Management) | 2 |
| `packages.config` (legacy) | `<package id="..." version="..." />` | 3 (best effort) |
| `Directory.Build.props` | только если содержит `PackageVersion`; иначе игнорируется | 2 |

**Правила:**

- XML-парсинг: `xml.etree.ElementTree` с отключёнными DTD/внешними сущностями;
  namespace MSBuild (`http://schemas.microsoft.com/developer/msbuild/2003`)
  снимается. Лимит файла **256 KiB**, глубина вложенности **64**, число
  `PackageReference`/`PackageVersion` на файл **2000**.
- Приоритет версии: `VersionOverride` → `Version` у `PackageReference` →
  `PackageVersion` из ближайшего `Directory.Packages.props` (поиск вверх до
  корня репозитория) → `packages.config` → `unknown`.
- `Version="$(Var)"`, `Condition=...`, `Import`, `Choose/When` **не
  вычисляются**. Пакет получает `status=unknown`, `current=null`,
  `kind=range` (в отчёте — причина `msbuild_property`/`conditional`).
- Форматы версий: `1.2.3` и `[1.2.3]` → `exact`; `[1.0,2.0)`, `1.*`, `*`,
  `1.2.*` → `range`; `ProjectReference`, `Reference`, локальные пути и
  `PackageReference` без версии при отсутствии CPM → `ignored`.
- Несколько `TargetFrameworks`/`RuntimeIdentifiers` не дублируют пакет:
  дедупликация по имени, `exact` важнее `range`; провенанс — `manifest_path`.
- `manifest_line` — 1-based строка XML-элемента (для `packages.config` — тоже);
  `manifest_section` — `PackageReference` / `PackageVersion` / `packages.config`.
- Ошибка XML (битый файл, DTD, превышение лимита) → ecosystem
  `status=parse_error`, остальные манифесты продолжают обрабатываться.
- `bin/`, `obj/`, `.vs/`, `packages/` (legacy restore) и `.git` игнорируются.

### 3.2. NuGet-клиент

**Новый провайдер:** `backend/app/providers/nuget_client.py`.

- `GET https://api.nuget.org/v3-flatcontainer/{id-lower}/index.json` →
  `{"versions": ["1.0.0", ...]}`; `id` нормализуется к нижнему регистру и
  URL-encode.
- `latest` — максимальная **stable**-версия по SemVer 2.0.0; prerelease
  (`-beta`, `-rc`) игнорируются. Если stable-версий нет — `latest=null`,
  `package.status=unknown` (без ошибки реестра).
- 404 → `not_found`: `latest=null`, `status=unknown`; 429/5xx — backoff
  0.5/1/2 с (max 3 попытки), затем `registry_unavailable`.
- Timeout `DEPENDENCY_HTTP_TIMEOUT` (default 5 с); concurrency
  `DEPENDENCY_CHECK_CONCURRENCY` (default 4); User-Agent `IIRuchating/1.3`.
- Кэш `dependency_cache`, ключ `nuget:<lower-id>`, TTL
  `DEPENDENCY_CACHE_TTL_SECONDS` (default 86400); stale-while-revalidate и
  single-flight — те же, что у PyPI/npm.
- Приватные фиды, `NuGet.config` credentials и аутентификация — вне scope.

**Согласование с существующими клиентами:** `PyPIClient`, `NpmClient` и
`NuGetClient` реализуют один контракт `get_latest(name) -> RegistryResult`
(`latest`, `source`, `error`), используют общий HTTP-layer, одинаковые
backoff/timeout/404-семантику и один кэш. `DependencyService` не знает о
формате ответа реестра.

### 3.3. CVE для NuGet

- `SecurityService`/`OsvClient` получают экосистему: для .NET в OSV
  передаётся `ecosystem="NuGet"`, имена пакетов — case-insensitive.
- `version_source`: `exact` для литерала/`[x.y.z]`, `lower_bound` для
  диапазона/CPM-диапазона.
- Пакеты без разрешимой версии (`$(...)`, condition, floating) попадают в
  `unknown_packages` с причиной `unresolved_version` — они **не** считаются
  проверенными.
- Кэш `security_cache`, ключ `osv:nuget:<lower-id>:<version>`; TTL 6 ч,
  batch ≤ 100, concurrency 4, лимиты — как в §3.16.
- `SecurityReport.ecosystems[]` получает третий элемент `ecosystem="dotnet"`,
  `manifest` — первый найденный `.csproj`/`Directory.Packages.props`.

### 3.4. UI: третья вкладка «C# / .NET»

- В блоке зависимостей (`DependencyPanel`/`RepositoryDetails`) — табы
  «Python / Node / C# / .NET»; сводка `all` включает третий ecosystem.
- Таблица: пакет, объявленная версия, текущая, последняя, статус, severity,
  манифест (строка), бейдж «CPM» для версии из `Directory.Packages.props`.
- Empty-state: «Манифесты .NET не найдены»; `parse_error` показывает причину
  и путь файла.
- RU/EN, `aria`, клавиатурная навигация по табам; бандл не растёт больше
  бюджета (ленивая загрузка панели сохраняется).

### 3.5. Обновление .NET-пакетов

Расширение `DependencyUpdateService` (SPEC §3.20):

- Read-only проверка: `dotnet list <project> package --outdated --no-restore`
  (только при наличии `dotnet` в PATH; результат — подсказка, не источник
  истины). Если `obj/project.assets.json` отсутствует — команда не запускается,
  используется отчёт NuGet-клиента.
- Мутация (только `confirm=true`, чистый worktree, `action_log` + `audit_log`):
  `dotnet add <project> package <id> --version <version> --no-restore`.
- Preflight: `dotnet` отсутствует → `409 dotnet_unavailable`; нет проекта →
  `409 no_manifest`; грязный worktree → `409 dirty_worktree`. Никаких
  `restore`/`build`/`publish`, `--force` и удаления lock-файлов.
- Timeout `DEPENDENCY_UPDATE_TIMEOUT_SECONDS` (180 с), output cap 10000
  символов, credentials редактируются. Ошибка команды — `ActionLog.status=error`,
  HTTP 409, без 500.
- UI: кнопка «Обновить» для выбранного пакета/всех outdated с предупреждением,
  что изменение `*.csproj` не коммитится автоматически.

### 3.6. Инсайты и RAG для C#

- `InsightsService` (hotspots): добавить `.cs`, `.csproj`, `.fsproj`,
  `.vbproj`, `.props`, `.targets` в учитываемые файлы; `bin/`, `obj/`,
  `.vs/` — в игнорируемые. Lock-файлы `packages.lock.json`,
  `project.assets.json` фильтруются.
- `CodeSearchService`: `.cs` → `csharp`, `.csproj`/`.fsproj`/`.vbproj`/`.props`
  → `xml`; `.razor`/`.cshtml` — кандидаты v1.4. Чанкинг — по классам/методам
  (эвристика по отступам и `{ }`), fallback — окно `RAG_CHUNK_CHARS`.
- Секреты в строках подключения (`Password=`, `AccountKey=`) маскируются;
  `.env`, `appsettings.*.json` с секретами не индексируются.
- Языковой фильтр `/search/code` принимает `csharp`, `xml`.

**DoD Sprint 57:** ✅

- [x] `DotnetParser` + тесты на реальных tmp-репозиториях: `.csproj` с
      `Version`, CPM, `VersionOverride`, `packages.config`, несколько
      `TargetFrameworks`, битый XML, DTD/XXE, `$(Property)`, condition,
      вложенные проекты и дедупликация.
- [x] `NuGetClient` с тем же контрактом, что `PyPIClient`/`NpmClient`; тесты
      stable/prerelease, 404, 429/5xx, timeout, кэш, stale.
- [x] `DependencyService` отдаёт `ecosystem="dotnet"`, `all` включает три
      экосистемы; `DependencyReport` и схемы расширены без breaking changes.
- [x] `SecurityService` проверяет NuGet через OSV (`ecosystem="NuGet"`),
      `unknown_packages` честно перечисляет неразрешимые версии.
- [x] UI: третья вкладка, CPM-бейдж, empty/error-состояния, RU/EN, `aria`.
- [x] `DependencyUpdateService`: `dotnet list --outdated --no-restore`, затем
      `dotnet add <project> package <id> --no-restore` только по `confirm=true`,
      с `action_log`; тесты на .NET и отсутствие проекта.
- [x] Hotspots и RAG видят `.cs`/`.fs`/`.csproj`; языковые фильтры работают.
- [x] `ruff`, `mypy --strict`, `pytest -q`, frontend typecheck/lint/test/build,
      bundle budget — зелёные.
- [x] ADR-0018 «.NET manifests & NuGet client» (XML-политика, CPM,
      ограничения MSBuild, отсутствие restore).

---

## 4. Sprint 58 — Team Edition & Audit Log (✅)

**Цель:** дать команде безопасную модель доступа (администратор и
наблюдатель/аудитор) и полный журнал действий.

### 4.1. Роли

- `users.role TEXT NOT NULL DEFAULT 'auditor'`, значения `admin` | `auditor`;
  миграция 013 переводит существующего пользователя в `admin`.
- Bootstrap-пользователь из `ADMIN_USERNAME` получает `admin`. При
  `AUTH_ENABLED=false` — неявный локальный `admin`.
- Роль читается из БД на каждом запросе; claim JWT `role` информационный и не
  является источником прав. Смена роли действует со следующего запроса.
- `GET /api/v1/auth/me` возвращает `{id, username, role, is_active,
  created_at, last_login_at}`.

**Матрица прав:**

| Возможность | `admin` | `auditor` |
|-------------|---------|-----------|
| Просмотр дашборда/репозиториев/зависимостей/CVE/insights/AI | ✅ | ✅ |
| Экспорт workspace/Markdown, чтение README/docs | ✅ | ✅ |
| `fetch`/`pull`/`push`/`stash`/`commit` | ✅ | ❌ `403 insufficient_role` |
| `update-dependencies`, bulk-actions | ✅ | ❌ |
| `automation/apply` (запись конфигурации) | ✅ | ❌ |
| Просмотр/изменение настроек, токенов, AI-профилей | ✅ (просмотр — и auditor) | ❌ изменение |
| Управление пользователями | ✅ | ❌ |
| Просмотр `audit_log` и экспорт | ✅ | ❌ |
| Запуск scan/SAST/индексации | ✅ | ❌ (только просмотр готовых отчётов) |

**Пользователи (admin-only):**

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| GET | `/api/v1/users` | — | `User[]` |
| POST | `/api/v1/users` | `{username, role, password?}` | `201 UserInviteResponse` |
| PATCH | `/api/v1/users/{id}` | `{role?, is_active?, password?}` | `User` |

- Пароль — bcrypt cost ≥ 12, минимум 8 символов; без пароля генерируется
  временный и возвращается один раз (`temporary_password`).
- Нельзя понизить/отключить себя и последнего активного `admin`
  (`409 cannot_demote_self` / `409 last_admin`).
- Ошибки: `400 validation_error`, `403 insufficient_role`, `404 user_not_found`,
  `409 username_exists`.
- `POST` и `PATCH` пишутся в `audit_log` (`user_created`, `role_changed`,
  `user_updated`).

### 4.2. Audit Log

**Назначение:** неизменяемый журнал security-relevant действий. Не заменяет
`action_log` (вывод команд): `audit_log` отвечает на «кто и что сделал», а
`action_log` — «что ответила команда».

**Схема:**

```
audit_log(
  id, user_id→users NULL,
  action TEXT, entity_type TEXT NULL, entity_id TEXT NULL,
  details JSONB, created_at
)
```

- `action` — стабильный код: `scan_started`, `repo_push`, `repo_<action>`,
  `dep_update`, `settings_updated`, `user_created`, `user_updated`,
  `role_changed`.
- `details` — только метаданные (например, `{"ecosystem": "dotnet",
  "status": "success"}`); секреты, токены, пароли, содержимое файлов и diff не
  пишутся; payload ≤ 4000 символов.
- Append-only: API только чтение; записи не обновляются и не удаляются
  приложением. Retention-политика — кандидат v1.3.0+.

**API (admin-only):**

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/api/v1/audit` | `limit? (1..200, default 50), offset?` | `AuditLogPage` |

`AuditLogPage`:

```json
{
  "items": [
    {
      "id": 1024,
      "created_at": "2026-11-11T09:15:00Z",
      "user": {"id": 2, "username": "auditor"},
      "action": "dep_update",
      "entity_type": "repository",
      "entity_id": "7",
      "details": {"ecosystem": "dotnet", "status": "success"}
    }
  ],
  "total": 1240,
  "limit": 50,
  "offset": 0
}
```

- Сортировка `created_at` desc, `id` desc.
- Доступ только `admin`; `auditor` получает `403 insufficient_role`.
- UI: страница `/admin/audit` (admin-only, lazy), таблица
  дата/пользователь/действие/объект/детали, пагинация, `aria`, пустое
  состояние.
- Индексы: `audit_log(created_at)`, `(user_id)`, `(action)`.

**DoD Sprint 58:** ✅

- [x] Миграция `users.role` (default `auditor`, существующий admin сохранён)
      + миграция `audit_log`; SQLite и PostgreSQL.
- [x] Зависимость `require_admin`; матрица прав покрыта тестами
      (auditor получает `403` на actions/settings/scan/users/audit).
- [x] `auth/me`, login и фронтенд показывают роль; `/admin/*` скрыт для
      auditor, сервер возвращает `403`.
- [x] Пользовательские эндпоинты (list/invite/update), bcrypt, защита
      последнего admin и self-demotion.
- [x] Audit-запись для scan, actions (`repo_push`/`repo_<action>`),
      update-dependencies (`dep_update`), settings, users/roles; `details`
      санитизируются.
- [x] `GET /audit` с пагинацией; секреты не попадают в `details`.
- [x] Тесты: роли, lockout, аудит настроек и ролей, пагинация, санитизация.
- [x] ADR-0019 «Roles and audit trail».
- [x] `ruff`, `mypy --strict`, `pytest -q`, frontend-проверки и bundle
      budget — зелёные.

---

## 5. Sprint 59 — Advanced Security (SAST) & Automated PRs (✅)

**Цель:** найти небезопасный код (а не только уязвимые зависимости) и упростить
подключение автоматических PR, не давая приложению права пушить.

### 5.1. SAST

**Новый сервис:** `backend/app/services/sast_service.py`.

| Инструмент | Языки | Запуск |
|------------|-------|--------|
| `bandit` | Python | `bandit -f json -q -r <repo>` |
| `semgrep` | Python/JS/TS/C# и др. | `semgrep --json --config <local-rules> --metrics=off --disable-version-check <repo>` |

- Инструменты — **внешние опциональные бинарники**, не Python-зависимости
  приложения (не добавляются в `requirements.txt`). Отсутствие бинарника →
  `tool.status=unavailable`, остальные инструменты работают; HTTP 200.
- Сеть запрещена: semgrep — только локальный набор правил
  (`SEMGREP_CONFIG_PATH` или bundled `security/`), без `--config auto`.
  `bandit` работает офлайн.
- Read-only: инструменты не пишут в репозиторий, не устанавливают пакеты и не
  исполняют код проекта. `GIT_OPTIONAL_LOCKS=0`; `obj/`, `bin/`,
  `node_modules/`, `.venv/`, `vendor/` исключаются.
- Лимиты: timeout `SAST_TIMEOUT_SECONDS` (default 120), вывод ≤ 8 MiB,
  findings ≤ `SAST_MAX_FINDINGS` (default 500). Превышение →
  `truncated=true`, `partial`.
- Нормализация: `{tool, rule_id, severity, confidence, file, line, column,
  message, cwe, category, snippet, fingerprint}`; severity маппится в общую
  шкалу `critical|high|medium|low|unknown` (bandit HIGH→high, MEDIUM→medium,
  LOW→low; semgrep ERROR→high, WARNING→medium, INFO→low).
- Дедупликация по `fingerprint = sha256(file+line+rule+message)`; один и тот
  же паттерн от bandit и semgrep показывается один раз с объединённым `tool`.
- `snippet` ≤ 300 символов, секреты маскируются; полные файлы и совпадения не
  логируются.
- Кэш `sast_cache` (TTL `SAST_CACHE_TTL_SECONDS`, default 86400), ключ
  `<repo_id>:<head_sha>:<dirty_hash>:<tools>`; `refresh=true` обходит TTL.
- Эндпоинт: `GET /api/v1/repositories/{id}/sast?tools=all|bandit|semgrep|eslint&
  min_severity=...&refresh=...` (контракт — SPEC §3.32).
- UI: отдельный блок «Безопасность кода (SAST)» рядом с CVE; severity,
  `файл:строка`, сниппет, кнопка «Исправить с AI», empty-state и `aria`.

**DoD SAST:** ✅

- [x] `SastService` с адаптерами bandit/semgrep/eslint, нормализацией,
      дедупликацией и fingerprint.
- [x] `GET /repositories/{id}/sast`, схема `SastReport`, `sast_cache` (24 ч).
- [x] Отсутствие инструмента/таймаут/большой вывод → partial HTTP 200, без 500.
- [x] Read-only: инструменты только читают файлы, `GIT_OPTIONAL_LOCKS=0`.
- [x] Тесты: парсинг bandit, severity, кэш/refresh, недоступные инструменты,
      таймаут, API/404.
- [x] Блок SAST, RU/EN, `aria`, ленивая загрузка, bundle budget.
- [x] ADR-0020 «SAST policy».

### 5.2. Automated PRs (Dependabot/Renovate)

**Назначение:** сгенерировать корректную конфигурацию автоматических PR для
выбранного репозитория. Приложение **не** делает commit/push и не создаёт PR —
это делают GitHub/GitLab после того, как пользователь закоммитит конфигурацию.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/api/v1/repositories/{id}/automation/generate` | `{tool: "dependabot" \| "renovate"}` | `AutomationConfigResponse` |

**`AutomationConfigResponse`:** `{tool, path, content, content_hash, warnings[],
ecosystems[]}`.

- `tool ∈ {dependabot, renovate}`; `ecosystems` — подмножество
  `python|node|dotnet` (по умолчанию — найденные манифесты).
- `path`: `.github/dependabot.yml` или `renovate.json`.
- Dependabot: `version: 2`, `updates[]` с `package-ecosystem`
  (`pip`/`npm`/`nuget`), `directory`, `schedule.interval=weekly`,
  `open-pull-requests-limit=5`, `groups` (minor/patch).
- Renovate: `$schema`, `extends: ["config:recommended"]`, `packageRules` для
  группировки minor/patch, `enabledManagers`.
- `content_hash = sha256(content)`.
- Эндпоинт только возвращает текст: файлы не пишутся, commit/push нет.
- Ошибки: `404 repository_not_found`, `422` — неверный `tool`.
- UI: lazy-модалка «Автоматизация» с генерацией, предпросмотром и копированием.

**DoD Automated PRs:** ✅

- [x] Генератор Dependabot/Renovate по найденным манифестам.
- [x] Эндпоинт не пишет файлы и не делает commit/push.
- [x] UI с предпросмотром, копированием и предупреждением об отсутствии
      автопуша; RU/EN, `aria`.
- [x] Тесты: python/node/dotnet, несколько экосистем, JSON Renovate,
      отсутствие записи, API/404.
- [x] ADR-0021 «Automation config generation (no push)».

### 5.3. Release v1.3.0 (✅)

- [x] Версии `1.3.0` в `backend/app/config.py`, `backend/app/__init__.py`,
      `backend/pyproject.toml`, `frontend/package.json`,
      `frontend/src-tauri/tauri.conf.json`, `frontend/src-tauri/Cargo.toml`.
- [x] `docs/CHANGELOG.md`, `docs/RELEASES.md`, README, SPEC, ARCHITECTURE
      согласованы; KI-025 остаётся актуальной или закрыта с обоснованием.
- [x] Миграции 013 (roles/audit) и 014 (sast_cache) проверены на SQLite.
- [ ] Тег `v1.3.0` запускает кросс-платформенный Release (Windows/macOS/Linux);
      артефакты, `.sig` и `latest.json` проверены.
- [ ] Финальный smoke: .NET-проект (dependencies/CVE/update), роли admin/auditor,
      audit log, SAST на Python/C#, preview/apply конфигурации, миграции
      SQLite/PostgreSQL.
- [x] Финальный аудит read-only: нет новых destructive-команд, кроме
      согласованных Actions.

---

## 6. Контракты и совместимость

| Объект | Контракт | Совместимость |
|--------|----------|---------------|
| `ecosystem` | `python \| node \| dotnet \| all` | `dotnet` — новое значение; `all` включает три экосистемы |
| `dependency_cache` | ключ `nuget:<lower-id>` | старые ключи `pypi:`/`npm:` не меняются |
| `security_cache` | ключ `osv:nuget:<lower-id>:<version>` | старые ключи не меняются |
| `NuGetClient` | `get_latest_version(name) -> PackageVersionResult` | идентичен `PyPIClient`/`NpmClient`: `latest`, `source`, `error` |
| `users` | `role ∈ {admin, auditor}` | default `auditor`; существующий пользователь миграцией переведён в `admin` |
| `audit_log` | append-only, admin-only API | новая таблица; `action_log` не меняется |
| `SastReport` | `{repository_id, checked_at, status, tools[], summary, findings[], truncated, error, cached}` | новое; `SecurityReport` не меняется |
| `AutomationConfig` | `{tool, path, content, content_hash, warnings, ecosystems}` | новое; файлы не пишутся |

**Трассировка:**

| Требование | SPEC | ARCHITECTURE | Спринт |
|------------|------|--------------|--------|
| .NET-манифесты и NuGet | §3.15, §3.15.1 | §11, §29 | 57 |
| CVE NuGet | §3.16 | §12, §29 | 57 |
| Обновление .NET-пакетов | §3.20 | §17, §29 | 57 |
| Hotspots/RAG для C# | §3.17, §3.26 | §13, §21 | 57 |
| Роли и права | §3.28, §3.31 | §31 | 58 |
| Audit Log | §3.31 | §31 | 58 |
| SAST | §3.32 | §30 | 59 |
| Автоматические PR | §3.33 | §32 | 59 |
| XML-сложность | §3.15.1 | §29 | 57 (KI-025) |

---

## 7. Риски и зависимости

| Риск | Влияние | Митигация |
|------|---------|-----------|
| Многоформатность .NET (`.csproj`, CPM, `packages.config`, props/targets) | Ложные `unknown`/пропущенные пакеты | KI-025; приоритет источников версии; честный `parse_error`/`unknown`; тесты на реальных проектах |
| MSBuild-свойства и conditions | Невозможно вычислить версию без MSBuild | Не угадывать: `unknown` + причина; MSBuild-evaluation вне scope |
| XML-атаки (XXE/DTD/billion laughs) | Чтение файлов/DoS | stdlib ET без DTD/сущностей, лимиты размера/глубины, тесты |
| NuGet API 429/5xx/404 | Неполный отчёт | кэш 24 ч, backoff, stale, concurrency 4, HTTP 200 |
| `dotnet` CLI отсутствует или меняет `obj/` | 409/грязный worktree | `--no-restore`, проверка PATH, preflight чистоты, предупреждение |
| Ошибка в модели ролей | Lockout/повышение прав | серверная проверка роли, запрет последнего admin, тесты матрицы, ADR |
| Утечка секретов в audit log | Компрометация | allowlist полей `details`, маскирование, тесты, append-only |
| SAST false positives / медленный скан | Шум/таймаут | severity/confidence, фильтры, лимиты, `truncated`, кэш |
| semgrep тянет правила из сети | Supply-chain/офлайн | только локальные правила, `--metrics=off`, без `--config auto` |
| Неверная конфигурация Dependabot/Renovate | Сломанные PR/CI | валидация синтаксиса, preview, allowlist, hash, никакого autopush |
| Auditor обходит ограничения через прямые API | Нарушение read-only | `require_admin` на мутациях, тесты `403`, аудит действий |
