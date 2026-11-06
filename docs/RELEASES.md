# RELEASES — Журнал спринтов

**Текущая версия:** v0.6.0 (2026-11-06)

---

## Спринт 33: AI Security Insights & Global Dashboard (v0.7.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S33-001: `GlobalAnalyticsService` — агрегация `DependencyService` по tracked-репозиториям, `distribution`, `latest_version`, `unification_needed`, кэш 1 час.
- [x] S33-002: `LLMService.explain_cve(cve_id, summary)` и `POST /repositories/{id}/ai/cve-explain`; `ai_cache` на 7 дней.
- [x] S33-003: `GET /api/v1/dashboard/global-dependencies` (`refresh`); ответ `{ecosystems: {python, node}}`.
- [x] S33-004: блок «Global Dependencies» на дашборде (бейдж «Унифицировать») и CVE-модалка «Объяснить» в деталях.
- [x] S33-005: `test_global_analytics.py` (6 тестов), `test_ai_explain.py` (7 тестов), SPEC §3.18.2/§3.19, ARCHITECTURE §15.4/§16.

### Результаты

- Backend-тесты: 198 passed
- Frontend-тесты: 36 passed
- Read-only: CVE explain/global analytics не меняют репозиторий.
- `ai_cache` хранит только текст объяснения; LLM-ошибка → `503`, без fallback-текста.

---

## Спринт 32: LLM Provider & AI Commit Messages (v0.7.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S32-001: `LLMService` — OpenAI-совместимый `POST /v1/chat/completions` (LM Studio/Ollama), timeout 30 с, remote-guard, очистка ответа; ошибки → `None`.
- [x] S32-002: settings `llm_enabled/base_url/model/api_key/timeout/max_diff_chars/allow_remote`, маскировка ключа, секция «AI / LLM» в UI.
- [x] S32-003: `git diff HEAD` + лимит 10000 символов с `[diff truncated]`, `CommitMessageSuggestion`.
- [x] S32-004: `POST /repositories/{id}/ai/commit-message`; `commit` в `ActionService` с `confirm=true`, сообщением и `action_log`.
- [x] S32-005: кнопка «Сгенерировать коммит», модалка с лоадером/textarea/копированием и подтверждённым коммитом, toast при ошибке LLM.
- [x] S32-006: `test_llm.py` (13 тестов), SPEC §3.18.1, ARCHITECTURE §15, ADR-0010, CHANGELOG/RELEASES.

### Результаты

- Backend-тесты: 188 passed
- Frontend-тесты: 34 passed
- Read-only: AI-эндпоинт не коммитит; `commit` — отдельное действие с подтверждением.
- Diff/промпты не логируются; `llm_api_key` маскируется.

---

## Релиз v0.6.0 — «Security & Insights»

**Дата:** 2026-11-06 · **Тег:** `v0.6.0`

Итоги этапа (спринты 27–30):

- **Planning (S27):** контракты и план v0.6.0, KI-011/012.
- **Supply Chain Security (S28):** CVE через OSV.dev, regex Secret Scanner, блок
  «Безопасность», `security_cache` 6 ч.
- **Tech Debt & Insights (S29):** hotspots по churn, DORA-lite commit frequency
  со sparkline, кэш 300 с и безопасный subprocess-runner.
- **Collaboration & Release (S30):** Markdown-сводка, Workspace export/import,
  версии 0.6.0, итоговый аудит и тег.
- **Итоговые тесты:** 175 backend + 32 frontend; entry bundle 85.62 kB gzip;
  `InsightsSparkline` — 6.55 kB gzip (lazy).

---

## Спринт 30: Collaboration & Release v0.6.0

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S30-001: кнопка «Скопировать сводку» на дашборде — Markdown текущего среза (summary, проблемные проекты, mirror-статусы) + toast.
- [x] S30-002: `getExportState`/`importState` в `useViewsStore` и `useTableStore`; экспорт/импорт `iiruchating_workspace.json` на странице настроек с валидацией версии и лимитом 1 MiB.
- [x] S30-003: версии `0.6.0` (backend/frontend), CHANGELOG `[0.6.0]`, RELEASES, README, SPEC §3.16–3.17 и §9.11.
- [x] S30-004: финальные проверки, тег `v0.6.0` в GitHub/GitFlic, GitHub Release.

### Результаты

- Backend-тесты: 175 passed
- Frontend-тесты: 32 passed
- Entry bundle: 85.62 kB gzip; `RepositoryDetails` — 9.37 kB, `InsightsSparkline` — 6.55 kB (lazy).
- Workspace export не содержит токенов и `SCAN_ROOTS`; импорт отклоняет чужую версию схемы.

---

## Спринт 29: Tech Debt & Insights (v0.6.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S29-001: `InsightsService` — churn hotspots (`git log --no-merges --name-only --since="3 months ago"`), топ-5, фильтры lock/docs/generated/удалённых файлов.
- [x] S29-001: DORA-lite commit frequency (`git log <branch> --format=%ad --date=short`) с заполнением пустых дней и summary `commits/per_day/per_week`.
- [x] S29-001: `asyncio.create_subprocess_exec` runner, `GIT_OPTIONAL_LOCKS=0`, timeout 10 с, лимит stdout 8 MiB, in-memory кэш 300 с.
- [x] S29-002: `GET /api/v1/repositories/{id}/insights` (`days`, `refresh`).
- [x] S29-003: UI — блоки «Технический долг (Hotspots)» и «Активность (30 дней)» с lazy `recharts` sparkline.
- [x] S29-004: тесты (`test_insights.py`), SPEC §3.17, ARCHITECTURE §13, CHANGELOG/RELEASES.

### Результаты

- Backend-тесты: 175 passed
- Frontend-тесты: 23 passed
- Entry bundle: 85.59 kB gzip; `InsightsSparkline` — 6.55 kB gzip (lazy), `RepositoryDetails` — 9.37 kB gzip.

---

## Спринт 28: Supply Chain Security (v0.6.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S28-001: `OsvClient` — `POST /v1/querybatch` (PyPI/npm), батчи по 100, retry/backoff, CVSS v3 base score из вектора.
- [x] S28-002: `SecurityService` — CVE для Python/Node-манифестов, `exact`/`lower_bound`/`unknown`, severity mapping, `security_cache` (TTL 6 ч) и stale-while-revalidate.
- [x] S28-002: базовый Secret Scanner — AWS Access Key/Secret, GitHub token, JWT, private key; только рабочая директория, маскирование, ignore-маркер, лимиты файлов/размера.
- [x] S28-003: `GET /api/v1/repositories/{id}/security` (`refresh`, `include_secrets`, `min_severity`).
- [x] S28-004: UI-блок «Безопасность» в деталях репозитория — severity-бейджи, CVE/OSV-ссылки, красный алерт о секретах.
- [x] S28-005: тесты (`test_security.py`), ADR-0009, SPEC §3.16, ARCHITECTURE §12, CHANGELOG.

### Результаты

- Backend-тесты: 164 passed
- Frontend-тесты: 20 passed
- Read-only: `pip`/`npm` не запускаются, история Git не сканируется; секреты только в masked preview.

---

## Релиз v0.5.0 — «Observability & Dependency Management»

**Дата:** 2026-11-06 · **Тег:** `v0.5.0`

Итоги этапа (спринты 24–26):

- **Dark Charts (S24):** M3-палитра recharts для light/dark, токены осей,
  сетки, тултипов и легенд.
- **Docker Integration (S24):** read-only Docker SDK, DooD через socket,
  статусы контейнеров, порты и `DOCKER_PATH_MAP`.
- **Dependency Management (S25):** парсер `requirements.txt`, PyPI-клиент,
  `dependency_cache` 24 ч, UI-блок и API.
- **Dependency Management (S26):** парсер `package.json`, npm-клиент,
  `ecosystem=all`, объединённый `summary`, табы Python/Node в UI.
- **Релиз (S26):** версии 0.5.0, docs-consistency audit, тег в GitHub и GitFlic.

**Итоговые метрики:** 148 backend-тестов, 17 frontend-тестов;
entry bundle 85.59 kB gzip, `RepositoryDetails` — 7.09 kB,
`DashboardCharts` — 114.55 kB gzip (lazy).

**Release smoke:** `/health` → `version=0.5.0`; `ecosystem=node` для
`ai-dzenwriter` → 9 пакетов, 2 outdated; `ecosystem=all` → `summary`
9/2 (Python no_manifest + Node); Docker-контейнеры проекта — `running`.

---

## Спринт 24: Dark Charts & Docker Integration (v0.5.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S24-001: M3-тема для recharts — оси, сетка, тултипы и легенды используют
  `surface`/`on-surface`, light/dark переключается без перезагрузки.
- [x] S24-002: `DockerService` на Python Docker SDK — read-only `ping` +
  `containers.list(all=True)`, `DockerStatus` (`running/stopped/not_found/unavailable`),
  кэш 30 с, `DOCKER_PATH_MAP`.
- [x] S24-003: DooD — `/var/run/docker.sock:ro`, `DOCKER_HOST`, конфигурация
  `PROJECTS_ROOT`; ошибки Docker не дают 5xx.
- [x] S24-004: UI-блок «Docker Containers» с бейджами, портами и ошибками;
  типы `DockerStatus` во frontend.
- [x] Тесты, SPEC §3.14, ARCHITECTURE §10, ADR-0007, CHANGELOG, KI-009.

### Метрики

- Backend: **131 passed** (включая 10 Docker-тестов на fake SDK).
- Frontend: **14 passed**; entry bundle **85.59 kB gzip**, `RepositoryDetails`
  — 5.45 kB, `DashboardCharts` — 114.55 kB gzip (lazy).
- Docker smoke: `GET /repositories/26/docker` → `running`, backend/frontend
  контейнеры, порты 8000/3000; `GET /repositories/1/docker` → `not_found`
  (у репозитория нет контейнеров).

---

## Спринт 25: Dependency Management (Python) (v0.5.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S25-001: `dependency_cache` + миграция `006`, TTL 24 ч, single-flight,
  stale-while-revalidate.
- [x] S25-002: безопасный парсер `requirements.txt` (`-r` include, cycles,
  path traversal, pins/ranges/extras/markers).
- [x] S25-003: PyPI-клиент с timeout, retry/backoff на 429/5xx и partial results.
- [x] S25-004: `GET /repositories/{id}/dependencies` с `refresh` и `ecosystem`.
- [x] S25-005: UI-блок «Зависимости» со счётчиками, severity и ссылками на PyPI.
- [x] S25-006: тесты парсера, кэша, single-flight, stale, API и UI.
- [x] S25-007: ADR-0008, SPEC §3.15, ARCHITECTURE §11, KI-010, CHANGELOG.

### Метрики

- Backend: **145 passed** (включая 14 dependency-тестов).
- Frontend: **16 passed**; entry bundle **85.59 kB gzip**,
  `RepositoryDetails` — 6.82 kB, `DashboardCharts` — 114.55 kB gzip (lazy).
- Smoke: временный root `requirements.txt` (fastapi==0.115.6, requests>=2.31)
  → `GET /repositories/26/dependencies?ecosystem=python&refresh=true` вернул
  `status=ok`, `source=registry`, 2 outdated; повторный запрос — `source=cache`.
  Файл после проверки удалён.

---

## Релиз v0.4.0 — «UX & Advanced Monitoring»

**Дата:** 2026-11-05 · **Тег:** `v0.4.0`

Итоги этапа (спринты 17–22):

- **Advanced Data Table (S18):** batch selection, bulk по выбранным, контекстное меню, управление колонками.
- **Filtering & Saved Views (S19):** filter chips, сохранённые представления, URL-состояние, CI-агрегат в dashboard.
- **Keyboard (S20):** Command Palette (`Ctrl/Cmd+K`), навигация по таблице, панель подсказок `?`.
- **Visuals/A11y (S21):** иконки статусов, stale-индикатор, Conflict Manager, contribution heatmap, экспорт CSV/JSON.
- **Notifications (S21):** Telegram Bot API вместо `plyer`; KI-007 и KI-008 закрыты.
- **Релиз (S22):** docs-consistency audit, тег `v0.4.0` в GitHub и GitFlic.

**Итоговые метрики:** 121 backend-тест, 11 frontend-тестов, entry ~86 kB gzip
(графики и Command Palette — отдельные lazy-chunks).

---

## Релиз v0.3.0 — «Productivity & UI»

**Дата:** 2026-11-05 · **Тег:** `v0.3.0`

Итоги этапа (спринты 13–16):

- **Bulk Actions (S13):** массовые `fetch_all`/`sync_mirrors_all` с `asyncio.Semaphore(5)` и фоновыми API.
- **Caching (S13):** TTL-кэш провайдеров (`PROVIDER_CACHE_TTL_SECONDS=60`).
- **UX/UI (S14):** тёмная тема, Pie/Bar-графики на recharts (lazy), поиск/сортировка, кликабельные строки.
- **Settings (S15):** `app_settings`, страница `/settings`, маскировка токенов, runtime-применение конфига.
- **Migration (S15):** массовая миграция `canonical_provider` на GitFlic через фоновый API.
- **Релиз (S16):** docs-consistency audit, тег `v0.3.0` в обоих провайдерах.

**Итоговые метрики:** 116 backend-тестов, 5 frontend-тестов, entry ~84 kB gzip
(графики — отдельный lazy-chunk).

---

## Релиз v0.2.0 — «Observability & Mirror»

**Дата:** 2026-11-05 · **Тег:** `v0.2.0`

Итоги этапа (спринты 7–12):

- **Стабилизация (S7):** закрыты KI-001…KI-003 — kill fetch по таймауту, быстрый dirty-check, TTL-кэш compare.
- **Observability (S8):** Prometheus `/api/v1/metrics`, расширенный `/health`, structlog-события.
- **Mirror GitHub ↔ GitFlic (S9):** 9 статусов зеркала, клиенты провайдеров, polling, webhooks с HMAC, UI-секция «Зеркала».
- **Actions (S10):** подтверждённые мутации `fetch/pull/push/stash/push_mirror`, аудит `action_log`, UI-модалка.
- **CI & Notifications (S11):** GitHub Actions CI-статус, desktop-уведомления, инструкция по webhook-туннелю.
- **Релиз (S12):** docs-consistency audit, тег `v0.2.0` в GitHub и GitFlic.

**Итоговые метрики:** 107 backend-тестов, 3 frontend-теста, entry bundle ~83 kB gzip;
Docker-сканирование `C:/Projects` через volume `/projects` (34 репозитория на dev-машине).

---

## Релиз v0.1.0 — MVP «Situational Awareness»

**Дата:** 2026-11-05 · **Тег:** `v0.1.0`

Что вошло в MVP:

- **Discovery** — поиск `.git` в `SCAN_ROOTS` с ограничением глубины и ignore-списком; запись `scan_runs`.
- **Status** — pygit2-снимок: ветка, upstream, detached, `modified/staged/untracked/conflicted`, `ahead/behind`.
- **Fetch** — `git fetch --all --prune` с таймаутом, graceful `remote_status=unavailable`, пересчёт через `rev-list`.
- **Dashboard** — сводка, фильтры, список репозиториев, track/untrack, детали с коммитами.
- **Recommendations** — команды по состоянию (commit/stash, rebase, push, pull, set-upstream) с копированием в UI; ничего не выполняется автоматически.
- **Docker** — Compose: backend (Python 3.12 + libgit2 + Alembic) и frontend (Node 20 build → nginx), SQLite-volume.
- **Brand** — палитра M3, Inter/Manrope, логотип из бренд-бука.

**Итоговые метрики:** 59 backend-тестов, 2 frontend-теста, entry bundle 83.3 kB gzip.

---

## Спринт 1: Discovery & Data Model

**Период:** 2026-11-03 — 2026-11-04
**Статус:** ✅ Завершён

### Задачи
- [x] S1-001: Модели `Repository`, `RepositoryStatus`, `ScanRun`
- [x] S1-002: Discovery Service (рекурсивный обход, `SCAN_DEPTH`, `SCAN_IGNORE`)
- [x] S1-003: API `/scan`, `/repositories`
- [x] S1-004: Тесты discovery на tmp-репозиториях

### Метрики
- Backend-тесты: 11 passed
- Найдено репозиториев в тестовом дереве: 100% корректно

---

## Спринт 2: Git Status & Каноническая модель

**Период:** 2026-11-04
**Статус:** ✅ Завершён

### Задачи
- [x] S2-001: `pygit2`-бэкенд: `status()`, dirty-разбор, detached, upstream
- [x] S2-002: Каноническая классификация `current/behind/ahead/diverged/dirty/...`
- [x] S2-003: `GET /repositories/{id}/status`
- [x] S2-004: Тесты на всех состояниях (8 сценариев)

### Метрики
- Backend-тесты: 30 passed
- Все 8 состояний покрыты тестами на реальных tmp-репозиториях

---

## Спринт 3: Remote Comparator & Fetch

**Период:** 2026-11-04
**Статус:** ✅ Завершён

### Задачи
- [x] S3-001: `git fetch --all --prune` с таймаутом
- [x] S3-002: `rev-list --left-right --count` → `ahead/behind`
- [x] S3-003: `remote_status` (ok/unavailable/stale)
- [x] S3-004: `GET /repositories/{id}/compare` и `/log` (pygit2)
- [x] S3-005: Тесты с bare-repo как remote

### Метрики
- Backend-тесты: 37 passed
- Fetch на локальных репозиториях: < 2 с

---

## Спринт 4: Dashboard & Frontend

**Период:** 2026-11-04 — 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S4-001: `GET /dashboard` — сводка
- [x] S4-002: Фильтры «Требуют внимания», «Не отслеживаются»
- [x] S4-003: Секция «Не отслеживаются» + track/untrack
- [x] S4-004: Детали репозитория (ahead/behind, файлы, коммиты)
- [x] S4-005: Кнопка «Обновить» + кэш `STATUS_TTL_SECONDS`

### Метрики
- Backend-тесты: 41 passed
- Frontend-тесты: 2 passed
- Entry bundle: 83.3 kB gzip

---

## Спринт 5: Recommendations & Полировка

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S5-001: `RecommendationService` — команды на основе состояния
- [x] S5-002: `GET /repositories/{id}/recommendations`
- [x] S5-003: Read-only аудит: ни одна операция не мутирует рабочую директорию
- [x] S5-004: Docker Compose + `.env.example`

### Метрики
- Backend-тесты: 59 passed
- Read-only аудит: 10 проверок passed
- Docker: `docker compose up -d --build`, UI на порту 3000

---

## Спринт 6: Релиз v0.1.0

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S6-001: Финальные проверки (ruff, mypy, pytest, typecheck, lint, test, build)
- [x] S6-002: Документация (README, SPEC, ARCHITECTURE, USER_GUIDE, GETTING_STARTED, RELEASES, CHANGELOG)
- [x] S6-003: Docs-consistency audit
- [x] S6-004: Тег `v0.1.0` + зеркалирование в GitFlic

### Метрики
| Показатель | Значение |
|------------|----------|
| Backend-тесты | 59 passed |
| Frontend-тесты | 2 passed |
| Entry bundle | 83.3 kB gzip |
| Docker | build + up проверены (UI :3000, API :8000) |

---

## Спринт 7: Стабилизация и технический долг (v0.2.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S7-001 (KI-001): таймаут fetch убивает процесс и логирует подсказку увеличить `FETCH_TIMEOUT`
- [x] S7-002 (KI-002): быстрый dirty-check `git status --porcelain -uno` перед `pygit2.status()`
- [x] S7-003 (KI-003): TTL-кэш `GET /repositories/{id}/compare` (60 с, инвалидация на refresh)
- [x] S7-004: документация (`FETCH_TIMEOUT`, `COMPARE_TTL_SECONDS`, KNOWN_ISSUES, CHANGELOG)

### Метрики
- Backend-тесты: 66 passed
- KI-001…KI-003: **Resolved**

---

## Спринт 8: Monitoring & Metrics (v0.2.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S8-001: Prometheus-метрики fetch/status duration, `repositories_total{state}`, `scan_duration_seconds`
- [x] S8-002: `GET /api/v1/metrics` (Prometheus text format, local-only)
- [x] S8-003: structlog JSON: `fetch_failed`, `status_slow`, `scan_completed`
- [x] S8-004: `/health` — `providers`, кэшированный `git_version`, `db_ok`
- [x] S8-005: `docs/MONITORING.md`, `SPEC §3.1`, тесты observability

### Метрики
- Backend-тесты: 69 passed

---

## Спринт 9: Mirror GitHub ↔ GitFlic (v0.2.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S9-001: поля mirror-политики в `repositories`, таблицы `repository_mirror_status` и `webhook_events`, миграция `003`
- [x] S9-002: `GitHubClient` — `get_branch`, `list_repos`, rate-limit
- [x] S9-003: `GitFlicClient` — `get_branch`, `list_repos`, rate-limit
- [x] S9-004: `MirrorService` — классификация 9 статусов, upsert, candidates
- [x] S9-005: API `/mirror`, `/mirror/refresh`, `PATCH /mirror-policy`
- [x] S9-006: `GET /mirror/candidates`
- [x] S9-007: `MirrorScheduler` (polling `MIRROR_POLL_INTERVAL_SECONDS`)
- [x] S9-008: webhooks GitHub/GitFlic (HMAC, `webhook_events`, инвалидация)
- [x] S9-009: UI — вкладка «Зеркала», панель и модалка политики
- [x] S9-010: метрики `mirror_status_total`, `mirror_check_duration_seconds`
- [x] S9-011: тесты сервиса/API/webhooks
- [x] S9-012: документация (SPEC §3.8, ARCHITECTURE §7, USER_GUIDE)

### Метрики
- Backend-тесты: 90 passed
- Frontend-тесты: 2 passed
- Entry bundle: 83.3 kB gzip

---

## Спринт 10: Мутации с подтверждением (v0.2.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S10-001: `POST /repositories/{id}/actions/{action}` с `confirm=true` (ADR-0003)
- [x] S10-002: действия `pull`, `push`, `stash`
- [x] S10-003: `POST /mirror/actions/push-mirror`
- [x] S10-004: UI «Выполнить» + модалка подтверждения
- [x] S10-005: аудит `action_log` + `GET /admin/actions`
- [x] S10-006: тесты действий на bare-remote

### Метрики
- Backend-тесты: 98 passed
- Frontend-тесты: 3 passed
- Docker: scanning host `C:/Projects` через volume `/projects`

---

## Спринт 11: CI-статус, уведомления, webhook-proxy (v0.2.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S11-001: `GET /repositories/{id}/ci-status` + GitHub Actions клиент + UI-виджет
- [x] S11-002: desktop-уведомления (`plyer`) с настройками и rate-limit
- [x] S11-003: документация webhook-туннеля (cloudflared/ngrok)
- [x] S11-004: инструкция по подключению webhook в GitHub/GitFlic

### Метрики
- Backend-тесты: 107 passed
- Frontend-тесты: 3 passed
- Entry bundle: ~83 kB gzip

---

## Спринт 13: Bulk Actions & Caching (v0.3.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S13-001: `BulkService` — массовые fetch/sync с `asyncio.Semaphore(5)`, фоновые API
- [x] S13-002: TTL-кэш провайдеров (`PROVIDER_CACHE_TTL_SECONDS=60`)
- [x] S13-003: UI Fetch All / Sync Mirrors + polling прогресса
- [x] S13-004: сортировка таблицы и поиск по имени/пути
- [x] S13-005: тесты, SPEC §3.11, CHANGELOG, RELEASES

### Метрики
- Backend-тесты: 111 passed
- Frontend-тесты: 4 passed
- Entry bundle: ~83 kB gzip

---

## Спринт 14: UX/UI & Dashboard Analytics (v0.3.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S14-001: тёмная тема (`dark` класс, localStorage, переключатель, dark-стили компонентов)
- [x] S14-002: аналитика — Pie Chart состояний и Bar Chart `mirror_status` (recharts, lazy)
- [x] S14-003: hover/кликабельные строки, бейджи зеркал
- [x] S14-004: тесты (charts + theme toggle), CHANGELOG/RELEASES

### Метрики
- Backend-тесты: 111 passed
- Frontend-тесты: 5 passed
- Entry bundle: 84.03 kB gzip; charts chunk (lazy): 114.34 kB gzip

---

## Спринт 15: Settings & Mass Migration (v0.3.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S15-001: `AppSetting` + миграция `005`, `SettingsService`, `GET/PATCH /settings`, маскировка токенов
- [x] S15-002: массовая миграция `canonical_provider → gitflic` + 202 background API
- [x] S15-003: страница `/settings`, ссылка в шапке, кнопка «Мигрировать на GitFlic» на дашборде
- [x] S15-004: тесты settings/migration, SPEC/CHANGELOG/RELEASES

### Метрики
- Backend-тесты: 116 passed
- Frontend-тесты: 5 passed
- Entry bundle: 84.18 kB gzip

---

## Спринт 18: Advanced Data Table (v0.4.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S18-001: Zustand `useTableStore` (selection, columns, widths) + persist v1
- [x] S18-002: batch selection + bulk API `repo_ids`
- [x] S18-003: контекстное меню (открыть/fetch/copy path)
- [x] S18-004: управление колонками, resize, моноширинный стиль
- [x] S18-005: тесты (selection/bulk-scope/context menu)

### Метрики
- Backend-тесты: 117 passed
- Frontend-тесты: 7 passed
- Entry bundle: 84.19 kB gzip; Dashboard chunk: 20.27 kB

---

## Спринт 19: Filtering & Saved Views (v0.4.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S19-001: filter chips (статус/зеркало/CI/untracked) + «Очистить всё»
- [x] S19-002: Saved Views (Zustand + persist, применение/удаление)
- [x] S19-003: URL-синхронизация фильтров, сортировки и поиска
- [x] S19-004: CI-агрегат в dashboard для CI-чипов (кэш 60 с)

### Метрики
- Backend-тесты: 117 passed
- Frontend-тесты: 8 passed
- Entry bundle: 84.53 kB gzip; Dashboard chunk: 26.36 kB

---

## Спринт 20: Keyboard Navigation & Command Palette (v0.4.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S20-001: Command Palette (`Ctrl/Cmd+K`) с репозиториями, страницами и действиями
- [x] S20-002: навигация по таблице (`↑/↓`, Enter, Space, `/`, Esc) + подсветка
- [x] S20-003: модалка горячих клавиш (`?`) и подсказка в футере

### Метрики
- Backend-тесты: 117 passed
- Frontend-тесты: 11 passed
- Entry bundle: 85.59 kB gzip; Command Palette chunk (lazy): 4.33 kB

---

## Спринт 21: Visuals, A11y & New Features (v0.4.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S21-001: A11y-иконки статусов, stale-индикатор (10 мин / remote stale)
- [x] S21-002: Conflict Manager (`/conflicts`, блок для `diverged`); KI-008 Resolved
- [x] S21-003: Telegram-уведомления вместо `plyer`; KI-007 Resolved
- [x] S21-004: contribution heatmap (`/dashboard/heatmap` + UI)
- [x] S21-005: экспорт CSV/JSON (`/repositories/export` + UI)
- [x] S21-006: тесты и документация

### Метрики
- Backend-тесты: 121 passed
- Frontend-тесты: 11 passed
- Entry bundle: 85.59 kB gzip; Dashboard chunk: 30.55 kB
