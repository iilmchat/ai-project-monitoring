# CHANGELOG — История версий

## [Unreleased]

—

## [0.6.0] - 2026-11-06

Безопасность цепочки поставок (CVE, секреты), технический долг и активность
(Hotspots, DORA-lite), совместная работа (Markdown, Workspace export).

### Добавлено

- feat(security): `OsvClient` — batch-запросы к OSV.dev, CVSS v3 base score, нормализация advisories (S28-001).
- feat(security): `SecurityService` — CVE для `requirements.txt`/`package.json`, `version_source=exact|lower_bound`, severity/fixed/CVE-алиасы, кэш `security_cache` 6 ч и stale-while-revalidate (S28-002).
- feat(security): regex Secret Scanner (AWS, GitHub token, JWT, private key) только по рабочей директории; маскирование, `# iiruchating:ignore-secret`, лимиты 5000 файлов / 1 MiB (S28-002).
- feat(api): `GET /api/v1/repositories/{id}/security` с `refresh`, `include_secrets`, `min_severity` (S28-003).
- feat(ui): блок «Безопасность» — severity-бейджи, CVE/OSV-ссылки, `fixed_version`, красный алерт о секретах с masked preview (S28-004).
- test(security): OSV-парсинг, CVSS, кэш/partial failure, secret-правила и маскирование, API-контракт (S28-005).
- feat(insights): `InsightsService` — churn hotspots за 3 месяца (`git log --name-only --no-merges`), топ-5 с фильтрацией lock/docs/generated/удалённых файлов (S29-001).
- feat(insights): DORA-lite commit frequency по дням с заполнением пустых дней и summary `commits/per_day/per_week` (S29-001).
- feat(insights): асинхронный `asyncio.create_subprocess_exec` runner, timeout 10 с, in-memory кэш 300 с, статусы `partial/no_branch/shallow_clone/timeout` (S29-001).
- feat(api): `GET /api/v1/repositories/{id}/insights` с `days` и `refresh` (S29-002).
- feat(ui): блоки «Технический долг (Hotspots)» и «Активность (30 дней)» — lazy `recharts` sparkline, счётчики churn и пустые состояния (S29-003).
- test(insights): парсинг git-log, фильтры, кэш, timeout/no_branch/shallow и реальный tmp-репозиторий (S29-004).
- feat(export): «Скопировать сводку» на дашборде — Markdown текущего среза (счётчики, проблемные проекты, mirror-статусы) + toast (S30-001).
- feat(workspace): экспорт/импорт UI-настроек в `iiruchating_workspace.json` — Saved Views, видимые колонки и ширины; валидация версии и лимит 1 MiB; токены/SCAN_ROOTS не экспортируются (S30-002).
- test(export): Markdown-форматирование/экранирование, workspace round-trip, отказ версии и импорт в Zustand-сторы (S30-001..S30-002).

### Документация

- docs(insights): SPEC §3.17 (фактические поля), ARCHITECTURE §13, CHANGELOG/RELEASES (S29-004).
- docs(security): SPEC §3.16 (фактические поля), ARCHITECTURE §12, ADR-0009, KI-011/012 в матрицу (S28-005).
- docs(planning): план v0.6.0 — supply-chain security (OSV.dev CVE, secret scanning), insights (hotspots, DORA-lite), collaboration/export; SPEC §3.16–3.17, ARCHITECTURE §12–14, KI-011/012 (S27-001..S27-003).
- docs(release): v0.6.0 — версии, README, RELEASES, итоговый docs-consistency audit (S30-003..S30-004).

## [0.5.0] - 2026-11-06

Наблюдаемость и управление зависимостями: тёмные графики M3, Docker-интеграция,
аудит Python- и Node-зависимостей.

### Добавлено

- feat(ui): M3-тема для recharts — оси, сетка, тултипы и легенды используют surface/on-surface, light/dark переключается без reload (S24-001).
- feat(docker): read-only Docker SDK интеграция — `GET /repositories/{id}/docker`, статусы `running/stopped/not_found/unavailable`, порты, health и compose-labels (S24-002).
- feat(docker): DooD — `/var/run/docker.sock:ro`, `DOCKER_HOST`, `DOCKER_PATH_MAP`; ошибки Docker не дают 5xx (S24-003).
- feat(ui): блок «Docker Containers» в деталях репозитория (S24-004).
- test(docker): fake Docker client, path mapping, cache/refresh и API-контракт.
- feat(deps): `dependency_cache` + миграция 006, TTL 24 ч, single-flight и stale-while-revalidate (S25-001).
- feat(deps): безопасный парсер `requirements.txt` — pins, ranges, extras, markers, `-r` include (S25-002).
- feat(deps): PyPI-клиент с timeout, retry/backoff на 429/5xx и partial results (S25-003).
- feat(deps): `GET /repositories/{id}/dependencies` с фильтром `ecosystem` (S25-004).
- feat(ui): блок «Зависимости» — счётчики, severity и ссылки на PyPI (S25-005).
- feat(deps): парсер `package.json` — `dependencies`/`devDependencies`, scoped/workspace/file/git (S26-001).
- feat(deps): npm registry client с timeout, retry/backoff и общим кэшем `npm:<name>` (S26-002).
- feat(deps): `ecosystem=all` и верхнеуровневый `summary` объединённого отчёта (S26-003).
- feat(ui): табы Python/Node и кнопка «Проверить всё» в блоке зависимостей (S26-003).
- test(deps): Node-парсер, npm-кэш, объединённый отчёт и API `ecosystem=all`.

### Документация

- docs(planning): план v0.5.0 — Dark Charts, Docker, зависимости Python/Node (S23-001..S23-003).
- docs(docker): SPEC §3.14, ARCHITECTURE §10, ADR-0007, KI-009.
- docs(deps): SPEC §3.15, ARCHITECTURE §11, ADR-0008, KI-010.

## [0.4.0] - 2026-11-05

UX/UI и продвинутый мониторинг: таблица, представления, палитра команд, A11y, конфликты, Telegram, heatmap и экспорт.

### Добавлено

- feat(a11y): иконки статусов (✓/↑/↓/⚠/!/✕), stale-индикатор 🕒 + opacity для данных старше 10 минут.
- feat(conflicts): `GET /repositories/{id}/conflicts` и блок Conflict Manager для `diverged`.
- feat(notify): Telegram Bot API (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`), logger fallback, `plyer` удалён (KI-007 Resolved).
- feat(activity): `GET /dashboard/heatmap` + contribution heatmap на дашборде.
- feat(export): `GET /repositories/export?format=csv|json` + кнопка «Экспорт» в UI.
- feat(keyboard): Command Palette (`Ctrl/Cmd+K`) — репозитории, страницы, scan/fetch/migrate.
- feat(keyboard): навигация по таблице `↑/↓`, `Enter`, `Space`, `/`, `Esc` + ring-подсветка.
- feat(keyboard): модалка горячих клавиш по `?` и подсказка в футере.
- feat(filters): filter chips (статус/зеркало/CI + untracked), OR внутри категории и AND между категориями.
- feat(views): сохранённые представления (фильтры, сортировка, колонки) в Zustand + localStorage.
- feat(url): синхронизация фильтров/поиска/сортировки с query string (`?status=…&mirror=…&q=…`).
- feat(dashboard): CI-агрегат в `GET /dashboard` (кэш 60 с) для CI-чипов и колонки.
- feat(table): batch selection (Zustand + persist), bulk fetch/sync по `repo_ids`, контекстное меню (open/fetch/copy path).
- feat(table): управление колонками (видимость/ширина, localStorage), моноширинные пути и SHA.

## [0.3.0] - 2026-11-05

Продуктивность и UI: массовые операции, тёмная тема, аналитика и настройки.

### Добавлено

- feat(settings): `app_settings` + `GET/PATCH /settings` с маскировкой токенов; значения подхватываются в конфиг при старте.
- feat(settings-ui): страница `/settings` (SCAN_ROOTS, токены, webhook secret, default provider) и ссылка в шапке.
- feat(migration): `POST /repositories/actions/migrate_to_gitflic` — массовый перевод canonical на GitFlic + отчёт.
- feat(ui): тёмная тема (`darkMode: 'class'`, ThemeProvider + localStorage, переключатель в шапке).
- feat(ui): аналитика дашборда — Pie Chart по состояниям и Bar Chart по `mirror_status` (recharts, lazy-загрузка).
- feat(ui): кликабельные строки таблицы, hover, поиск/сортировка, dark-варианты бейджей и модалок.
- feat(bulk): `POST /repositories/actions/fetch_all` и `/sync_mirrors_all` — фоновые массовые операции с `asyncio.Semaphore(5)`; sync пишет `action_log`.
- feat(cache): TTL-кэш провайдеров (`PROVIDER_CACHE_TTL_SECONDS=60`) для branch/list запросов GitHub/GitFlic.
- feat(ui): панель Fetch All / Sync Mirrors с polling каждые 2 с, поиск по имени/пути и сортировка таблицы.

## [0.2.0] - 2026-11-05

Наблюдаемость, зеркалирование GitHub ↔ GitFlic и безопасные мутации.

### Добавлено

- feat(ci): CI status GitHub Actions (`/repositories/{id}/ci-status`) + widget в UI; GitFlic — `not_supported`.
- feat(notify): desktop-уведомления (plyer) для `history_rewritten`/`missing_on_*`/`behind_gitflic` и `remote_status=unavailable` (rate-limit 1/час); настройки `NOTIFICATIONS_ENABLED`/`NOTIFY_ON`.
- feat(actions): явные мутации с `confirm=true` — `fetch`, `pull`, `push`, `stash`, `push_mirror`; аудит `action_log`, `GET /admin/actions`; UI-кнопка «Выполнить» с модалкой подтверждения.
- feat(mirror): межпровайдерное зеркало GitHub ↔ GitFlic — `repository_mirror_status`, `webhook_events`, миграция `003`.
- feat(mirror): клиенты GitHub/GitFlic (`get_branch`, `list_repos`, rate-limit → `unavailable`), `MirrorService` (9 статусов) и `MirrorScheduler` (polling 300 с).
- feat(mirror): API `GET/POST /repositories/{id}/mirror`, `PATCH /mirror-policy`, `GET /mirror/candidates`, webhooks с HMAC.
- feat(mirror): UI — вкладка «Зеркала», панель зеркала, настройка политики, копирование рекомендаций.
- feat(obs): Prometheus-метрики `/api/v1/metrics` — fetch/status histograms, `repositories_total{state}`, `scan_duration_seconds`.
- feat(obs): расширенный `/health` — `providers` (github/gitflic), `git_version` кэшируется при старте.
- feat(obs): structlog-события `fetch_failed` (с `remote_url`), `status_slow` (> 1 с), `scan_completed` с длительностью.

### Изменено

- fix(docker): каталог проектов монтируется как `C:/Projects:/projects`, `SCAN_ROOTS=/projects`; `git safe.directory` в образе.
- chore(ui): брендинг переименован в **ai-project-monitoring** (title, шапка, футер).
- perf: fast dirty check (KI-002) — `git status --porcelain -uno` перед `pygit2.status()`; чистый tracked-статус не грузит CPU.
- feat: compare cache (KI-003) — TTL-кэш `GET /repositories/{id}/compare` (60 с, инвалидация на refresh).
- fix: fetch timeout cleanup (KI-001) — таймаут fetch убивает процесс (`proc.kill()`), логирует подсказку увеличить `FETCH_TIMEOUT`.

## [0.1.0] - 2026-11-05

Первый MVP: сканирование, локальный статус, сравнение с удалённым, дашборд и рекомендации. Read-only.

### Добавлено

- **Discovery:** рекурсивный поиск `.git` в `SCAN_ROOTS` с `SCAN_DEPTH` и `SCAN_IGNORE` (case-insensitive, без входа в `.git`); запись истории в `scan_runs`; проверка глубины и вложенных репозиториев.
- **Data model:** SQLAlchemy 2.0 модели `Repository`, `RepositoryStatus`, `ScanRun`; Alembic-миграции `001` (таблицы) и `002` (поля git-статуса).
- **Git-абстракция:** `pygit2` для status/discovery/log/compare; shell `git` (subprocess, `asyncio.to_thread`) для `fetch --all --prune` и `rev-list`.
- **Канонический статус:** `current / behind / ahead / diverged / dirty / no_upstream / detached / error`; приоритет `detached → no_upstream → dirty → diverged → ahead → behind → current`; `ahead/behind` по локальным refs и после fetch.
- **Remote:** таймаут `FETCH_TIMEOUT`; ошибка/таймаут fetch → `remote_status=unavailable` без 500; успех → `ok`; без fetch → `stale`.
- **API (`/api/v1`):** `GET /health`, `POST /scan`, `GET /scan/{id}`, `GET /scan/latest`, `GET /repositories` (+ пагинация), `POST /repositories/{id}/track|untrack`, `GET /repositories/{id}/status|compare|log|recommendations`, `POST /repositories/{id}/refresh`, `GET /dashboard`.
- **Кэш статуса:** in-memory TTL + свежесть `checked_at` из БД (`STATUS_TTL_SECONDS=60`); `POST /refresh` обходит кэш.
- **Рекомендации:** `commit/stash`, `pull --rebase`, `push`, `pull`, `set-upstream` — только текст, без выполнения.
- **Frontend:** React 19 + Vite 8 + TypeScript, Tailwind; дашборд со сводкой и фильтрами «Все / Требуют внимания / Не отслеживаются», скан, таблица, track; страница деталей с коммитами и блоком «Рекомендации» (кнопка «Копировать»).
- **Бренд:** логотип, favicon, палитра M3 и шрифты Inter/Manrope.
- **Docker:** `backend/Dockerfile` (Python 3.12, libgit2, Alembic перед запуском), `frontend/Dockerfile` (Node 20 → nginx), `docker-compose.yml`, SPA-fallback и прокси `/api`.
- **Тесты:** 59 backend (реальные tmp-репозитории, bare-remote), 2 frontend (Vitest + Testing Library), read-only аудит кода.

### Ограничения

- Мутации (`pull`/`push`) не реализованы — только рекомендации (ADR-0003).
- Mirror GitHub ↔ GitFlic (`mirror_status`, polling, webhook) — v0.2.0.
- GitHub/GitFlic Compare API не используется; сравнение локальное (pygit2).
- История статусов не ведётся (только последний снимок).
- Покрытие кода в v0.1.0 не измерялось (`pytest-cov` не подключён).
