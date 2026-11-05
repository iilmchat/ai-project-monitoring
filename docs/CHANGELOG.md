# CHANGELOG — История версий

## [Unreleased]

### Добавлено

- feat(ui): M3-тема для recharts — оси, сетка, тултипы и легенды используют surface/on-surface, light/dark переключается без reload (S24-001).
- feat(docker): read-only Docker SDK интеграция — `GET /repositories/{id}/docker`, статусы `running/stopped/not_found/unavailable`, порты, health и compose-labels (S24-002).
- feat(docker): DooD — `/var/run/docker.sock:ro`, `DOCKER_HOST`, `DOCKER_PATH_MAP`; ошибки Docker не дают 5xx (S24-003).
- feat(ui): блок «Docker Containers» в деталях репозитория (S24-004).
- test(docker): fake Docker client, path mapping, cache/refresh и API-контракт.

### Документация

- docs(planning): план v0.5.0 — Dark Charts, Docker, зависимости Python/Node (S23-001..S23-003).
- docs(docker): SPEC §3.14, ARCHITECTURE §10, ADR-0007, KI-009.

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
