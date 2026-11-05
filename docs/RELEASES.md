# RELEASES — Журнал спринтов

**Текущая версия:** v0.1.0 (2026-11-05)

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
- Backend-тесты: 28 passed
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
- Backend-тесты: 52 passed
- Покрытие: 74%

---

## Спринт 3: Remote Comparator & Fetch

**Период:** 2026-11-04
**Статус:** ✅ Завершён

### Задачи
- [x] S3-001: `git fetch --all --prune` с таймаутом
- [x] S3-002: `rev-list --left-right --count` → `ahead/behind`
- [x] S3-003: `remote_status` (ok/unavailable/stale)
- [x] S3-004: GitHub Compare API (опционально, с токеном)
- [x] S3-005: Тесты с bare-repo как remote

### Метрики
- Backend-тесты: 68 passed
- Fetch на 10 репозиториях: < 2 с (локально)

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
- Frontend-тесты: 30 passed
- Entry bundle: 68 kB gzip

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
- Backend-тесты: 80 passed
- Покрытие: 71%

---

## Спринт 6: Релиз v0.1.0

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S6-001: Финальные проверки (ruff, mypy, pytest, typecheck, lint, test, build)
- [x] S6-002: Документация (README, SPEC, ARCHITECTURE, USER_GUIDE, GETTING_STARTED, RULES)
- [x] S6-003: Тег `v0.1.0`

### Метрики
| Показатель | Значение |
|------------|----------|
| Backend-тесты | 80 passed |
| Frontend-тесты | 30 passed |
| Покрытие backend | 71% |
| Покрытие frontend | 62% |
| Entry bundle | 68 kB gzip |