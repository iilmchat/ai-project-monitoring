# CHANGELOG — История версий

## [Unreleased]

### Добавлено

- feat(actions): явные мутации с `confirm=true` — `pull`, `push`, `stash`, `push-mirror`; аудит `action_log`, `GET /admin/actions`; UI-кнопка «Выполнить» с модалкой подтверждения.
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
