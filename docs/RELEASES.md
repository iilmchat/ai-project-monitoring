# RELEASES — Журнал спринтов

**Текущая версия:** v0.1.0 (2026-11-05)

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