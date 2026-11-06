# TODO — план развития IIRuchating

**Текущая версия:** v0.7.0 (релиз 2026-11-06)
**Текущий этап:** v0.7.0 «AI & Global Analytics» — [`TODO_V0.7.md`](TODO_V0.7.md) (Sprint 34 завершён)
**Предыдущий этап:** v0.6.0 — [`TODO_V0.6.md`](TODO_V0.6.md)
**Дальше:** v0.8.0+ — идеи из раздела 6
**Последнее обновление:** 2026-11-06

---

## 0. Цели проекта (краткая шпаргалка)

| # | Цель | Критерий достижения |
|---|------|---------------------|
| G1 | Не терять работу в локальных репозиториях | `dirty`/`ahead` видны без ручного обхода |
| G2 | Понимать «куда двигаться дальше» | рекомендации с готовыми командами |
| G3 | Держать GitHub и GitFlic в согласованном состоянии | `mirror_status` для всех `mirror_expected=true` |
| G4 | Не пропускать новые/забытые репозитории | секция «Не отслеживаются» |
| G5 | Не терять саму документацию проекта | проект в GitHub (private) + зеркало в GitFlic |

---

## 1. Принцип планирования

1. **Bootstrap** — один раз, до всех спринтов (git init, GitHub, GitFlic, CI).
2. **MVP (v0.1.0)** — минимально работающий дашборд: discovery, локальный статус, сравнение с remote, рекомендации, read-only.
3. **Стабилизация (v0.2.0, спринт 7)** — закрыть KI-001…KI-003.
4. **Observability (спринт 8)** — метрики, логи, health.
5. **Mirror (спринт 9)** — GitHub ↔ GitFlic (ADR-0005), polling + webhook.
6. **Автоматизация (спринт 10)** — мутации только с `confirm=true`.
7. **Интеграции (спринт 11)** — CI-статус, уведомления, reverse-proxy для webhook.
8. **Релиз (спринт 12)** — тег `v0.2.0` + docs-consistency audit.

Правило: **следующий спринт не начинается, пока предыдущий не закрыт по DoD.**

---

## 2. Bootstrap (B-001…B-007) — выполняется один раз человеком

| ID | Задача | Зависит от | Ответственный |
|----|--------|------------|---------------|
| B-001 | Создать локальную директорию, `git init -b main`, `.gitignore`, `.env.example` | — | Человек |
| B-002 | Скопировать все документы (`README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `TODO.md`, `docs/**`) | B-001 | Человек |
| B-003 | Первый коммит `chore: initial scaffold with documentation` | B-002 | Человек |
| B-004 | Создать `iilmchat/iiruchating` в GitHub (**private**) и push `main` | B-003 | Человек |
| B-005 | Добавить `.github/workflows/ci.yml` (минимальный) и push | B-004 | Человек / OpenCode |
| B-006 | Импортировать проект в GitFlic (private), сверить `SHA(main)` | B-004 | Человек |
| B-007 | Зафиксировать процесс зеркалирования в `docs/GETTING_STARTED.md` §«Зеркалирование» | B-006 | Человек |

**DoD bootstrap:**
- `main` в GitHub и GitFlic указывают на **один и тот же SHA**.
- CI в GitHub зелёный (даже если это no-op job — важен факт запуска).
- В диффе нет секретов (`.env` только в `.gitignore`, `.env.example` — placeholders).
- В GitFlic есть зеркало `iiruchating` (private).
- В `docs/GETTING_STARTED.md` описан процесс зеркалирования.

---

## 3. v0.1.0 «Situational Awareness» (спринты 1–6) — MVP

> Цель: дашборд, который показывает локальное состояние всех репозиториев и
> сравнивает с remote. Read-only. Без mirror (mirror — v0.2.0).

### Спринт 1: Discovery & Data Model

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S1-001 | Модели `Repository`, `RepositoryStatus`, `ScanRun` + Alembic-миграция 001 | — | 1 д |
| S1-002 | `DiscoveryService`: рекурсивный обход, `SCAN_DEPTH`, `SCAN_IGNORE`, параллелизм `SCAN_CONCURRENCY` | S1-001 | 2 д |
| S1-003 | API `POST /scan`, `GET /scan/{id}`, `GET /scan/latest`, `GET /repositories` | S1-002 | 1 д |
| S1-004 | Тесты discovery на tmp-репозиториях (вложенность, исключения, глубина) | S1-002 | 1.5 д |
| S1-005 | `GET /health` с `git_version`, `scan_roots`, `db_ok` | — | 0.5 д |

**DoD:** на тестовом дереве из 10 репозиториев находит ровно 10; не уходит глубже `SCAN_DEPTH`; исключения работают; `pytest -q` зелёный.

### Спринт 2: Git Status & Каноническая модель

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S2-001 | `pygit2_backend`: `status()`, разбор `modified/staged/untracked/conflicted`, `detached`, upstream | S1-001 | 2 д |
| S2-002 | `StatusService`: каноническая классификация `current/behind/ahead/diverged/dirty/no_upstream/detached/error` | S2-001 | 1 д |
| S2-003 | API `GET /repositories/{id}/status`, `POST /repositories/{id}/refresh` | S2-002 | 1 д |
| S2-004 | Тесты на всех 8 состояниях (tmp + bare-remote) | S2-002 | 2 д |
| S2-005 | Кэш `STATUS_TTL_SECONDS` (60 с) | S2-003 | 0.5 д |

**DoD:** все 8 состояний воспроизводятся в тестах; `state` ортогонален `dirty`/`ahead/behind`; кэш работает.

### Спринт 3: Remote Comparator & Fetch

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S3-001 | `git fetch --all --prune` с таймаутом (`FETCH_TIMEOUT=30`) | S2-003 | 1 д |
| S3-002 | `git rev-list --left-right --count HEAD...@{u}` → `ahead/behind` | S3-001 | 0.5 д |
| S3-003 | `remote_status` (`ok/unavailable/stale`); fallback на локальные `refs/remotes/*` | S3-001 | 1 д |
| S3-004 | API `GET /repositories/{id}/compare`, `GET /repositories/{id}/log` | S3-002 | 1 д |
| S3-005 | Тесты с bare-repo как remote (ahead/behind/diverged) | S3-001…S3-004 | 2 д |

**DoD:** `ahead/behind` точны после fetch; при недоступном remote — `unavailable`, без падения; тесты на реальном bare-remote.

### Спринт 4: Dashboard & Frontend

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S4-001 | API `GET /dashboard` (сводка + список) | S2-003, S3-004 | 1 д |
| S4-002 | React-каркас, страница дашборда, фильтры «Все / Требуют внимания / Не отслеживаются / Чистые» | S4-001 | 2 д |
| S4-003 | Секция «Не отслеживаются» + `POST /repositories/{id}/track` / `untrack` | S1-003, S4-002 | 1 д |
| S4-004 | Детали репозитория (ветка, upstream, ahead/behind, файлы, коммиты) | S4-002 | 1.5 д |
| S4-005 | Кнопка «Обновить» (`POST /refresh`) | S4-004 | 0.5 д |
| S4-006 | Тесты frontend (Vitest): дашборд, фильтры, track/untrack | S4-002…S4-005 | 1.5 д |

**DoD:** дашборд показывает все репозитории; фильтры работают; «Не отслеживаются» видны; entry bundle ≤ 80 kB gzip.

### Спринт 5: Recommendations & Полировка

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S5-001 | `RecommendationService`: генерация команд по состоянию (`diverged → pull --rebase`, `ahead → push`, `dirty → stash/commit`) | S2-002 | 1.5 д |
| S5-002 | API `GET /repositories/{id}/recommendations` | S5-001 | 0.5 д |
| S5-003 | Read-only аудит: grep destructive-команд, тест-«канарейка» | S5-001 | 1 д |
| S5-004 | Docker Compose (backend + frontend + SQLite-volume), `.env.example` | S4-002 | 1 д |
| S5-005 | Тесты: рекомендации для всех состояний; read-only подтверждён | S5-001…S5-003 | 1.5 д |

**DoD:** рекомендации точны; ни одна операция чтения не мутирует рабочую директорию (проверено grep'ом + тестом).

### Спринт 6: Релиз v0.1.0

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S6-001 | Финальные проверки (`ruff`, `mypy --strict`, `pytest -q`, `pnpm typecheck/lint/test/build`) | S1–S5 | 1 д |
| S6-002 | Документация: `CHANGELOG [0.1.0]`, `RELEASES` (S1–S6), `SPEC`, `ARCHITECTURE`, `USER_GUIDE`, `GETTING_STARTED` | S6-001 | 1 д |
| S6-003 | Docs-consistency audit (`docs/prompts/docs-consistency-audit.md`) — DSH | S6-002 | 0.5 д |
| S6-004 | Тег `v0.1.0`, зеркалирование в GitFlic, проверка `SHA(main)` совпадает | S6-003 | 0.5 д |

**DoD:** все проверки зелёные; документация согласована; тег `v0.1.0` в GitHub и GitFlic; `mirror_status=in_sync` (вручную).

---

## 4. v0.2.0 «Observability & Mirror» (спринты 7–12)

### Спринт 7: Стабилизация и технический долг

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S7-001 | KI-001: адаптивный таймаут fetch (замер, увеличение для больших репо) | — | 1 д |
| S7-002 | KI-002: быстрый `status` через `git status --porcelain -uno` для «грязный/чистый» | S7-001 | 2 д |
| S7-003 | KI-003: кэш результатов Compare API (провайдерский) | — | 1 д |
| S7-004 | `FETCH_TIMEOUT` в `.env.example` и `GETTING_STARTED` | S7-001 | 0.5 д |

**DoD:** все три KI закрыты; `pytest -q` зелёный; документация обновлена.

### Спринт 8: Monitoring & Metrics (ADR-0004)

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S8-001 | Prometheus-метрики: `fetch_duration`, `status_duration`, `repositories_total{state}` | — | 2 д |
| S8-002 | `GET /metrics` (Prometheus text format, local-only) | S8-001 | 0.5 д |
| S8-003 | `structlog` JSON: `fetch_failed`, `status_slow`, `scan_completed` | — | 1 д |
| S8-004 | Расширить `/health`: `git_version`, `db_ok`, `providers{github,gitflic}` | S8-001 | 0.5 д |
| S8-005 | `docs/MONITORING.md`: SLI/SLO, метрики, логи, алерты | S8-001…S8-004 | 1 д |

**DoD:** `/metrics` отдаёт метрики; логи JSON; MONITORING.md описывает SLI/SLO.

### Спринт 9: Mirror GitHub ↔ GitFlic (R8/R9, ADR-0005)

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S9-001 | Модели `repository_mirror_status`, `webhook_events` + поля `repositories` (canonical/expected/policy) + миграция | — | 1 д |
| S9-002 | `GitHubClient`: `get_branch`, `list_repos`, `compare` (rate-limit, retry, backoff) | — | 2 д |
| S9-003 | `GitFlicClient`: `get_branch`, `list_projects`, `compare` (аналогично) | — | 2 д |
| S9-004 | `MirrorService.classify` + `refresh` + `upsert` | S9-001…S9-003 | 2 д |
| S9-005 | API `GET /repositories/{id}/mirror`, `POST /mirror/refresh`, `PATCH /mirror-policy` | S9-004 | 1 д |
| S9-006 | API `GET /mirror/candidates` (дедупликация по name, `suggested_action`) | S9-004 | 1.5 д |
| S9-007 | `MirrorScheduler` (polling 300 с, замедление при rate-limit) | S9-004 | 1 д |
| S9-008 | Webhook-эндпоинты (HMAC, `202 до обработки`, запись `webhook_events`) | S9-004 | 1.5 д |
| S9-009 | UI: секция «Зеркала», модалка политики, фильтр «Зеркала расходятся» | S9-005, S9-006 | 2 д |
| S9-010 | Метрики `mirror_status_total{status}`, `mirror_check_duration_seconds` | S9-004 | 0.5 д |
| S9-011 | Тесты: mock-API GitHub/GitFlic, классификация, rate-limit, webhook | S9-001…S9-010 | 2.5 д |
| S9-012 | Документация: SPEC §3.8, ARCHITECTURE §7, ADR-0005, USER_GUIDE | S9-001…S9-011 | 1 д |

**DoD:**
- `mirror_status` заполняется для всех `tracked=true ∧ mirror_expected=true`.
- `in_sync / missing_on_* / behind_* / diverged / history_rewritten / unavailable` различаются.
- Polling + webhook работают; webhook инвалидирует кэш и не блокирует ответ.
- `GET /mirror/candidates` возвращает `github_only / gitflic_only / both / unknown`.
- UI: зеркала видны отдельно, политика настраивается.
- Тесты ≥ 70% для mirror-слоя; mock-API покрывает rate-limit и 5xx.
- Документация обновлена.

### Спринт 10: Мутации с подтверждением

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S10-001 | `POST /repositories/{id}/actions/{action}` с `confirm=true` (ADR-0003) | S9-004 | 2 д |
| S10-002 | Действия: `pull`, `push`, `stash` (fetch уже есть) | S10-001 | 2 д |
| S10-003 | `POST /mirror/actions/{action}` — push зеркала (`git push gitflic main`) | S10-001, S9-004 | 1 д |
| S10-004 | UI: «Выполнить» с модалкой подтверждения | S10-001 | 1.5 д |
| S10-005 | Аудит действий (`action_log`) + `GET /admin/actions` | S10-001 | 1 д |
| S10-006 | Тесты: мутации на bare-remote | S10-001…S10-005 | 2 д |

**DoD:** мутации только после `confirm=true`; аудит пишется; push зеркала доступен из рекомендаций.

### Спринт 11: CI-статус, уведомления, reverse-proxy для webhook

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S11-001 | `GET /repositories/{id}/ci-status` (GitHub Actions / GitFlic CI) | S9-002, S9-003 | 2 д |
| S11-002 | Уведомления: desktop (`plyer`) или webhook; триггеры `NOTIFY_ON` | S9-008 | 2 д |
| S11-003 | ADR-0006: reverse-proxy для webhook (basic-auth + allowlist / `cloudflared`) | — | 1 д |
| S11-004 | Реализация ADR-0006 (dev + prod) | S11-003 | 2 д |

**DoD:** CI-статус виден в карточке; уведомления по `history_rewritten` / `missing_on_*`; webhook принимается через reverse-proxy.

### Спринт 12: Релиз v0.2.0

| ID | Задача | Зависит от | Оценка |
|----|--------|------------|--------|
| S12-001 | Финальные проверки (`ruff`, `mypy`, `pytest`, `pnpm`) | S7–S11 | 1 д |
| S12-002 | Обновить `CHANGELOG [0.2.0]`, `SPEC`, `ARCHITECTURE`, `USER_GUIDE`, `RELEASES` | S7–S11 | 1 д |
| S12-003 | Docs-consistency audit (`docs/prompts/docs-consistency-audit.md`) — DSH | S7–S11 | 0.5 д |
| S12-004 | Тег `v0.2.0` + зеркалирование в GitFlic, проверка `SHA(main)` | S12-001…S12-003 | 0.5 д |

**DoD:** все проверки зелёные; документация согласована; тег `v0.2.0` в обоих провайдерах; `mirror_status=in_sync` (через сам IIRuchating).

---

## 5. v0.3.0 «Productivity & UI» (спринты 13–16) — завершён

### Спринт 13: Bulk Actions & Caching
- [x] S13-001: `BulkService` — fetch/sync по всем репозиториям, `asyncio.Semaphore(5)`, фоновые API.
- [x] S13-002: TTL-кэш провайдеров (`PROVIDER_CACHE_TTL_SECONDS=60`).
- [x] S13-003: UI Fetch All / Sync Mirrors + polling прогресса.
- [x] S13-004: сортировка таблицы и поиск по имени/пути.
- [x] S13-005: тесты и документация.

### Спринт 14: UX/UI & Dashboard Analytics
- [x] S14-001: тёмная тема (class-стратегия, localStorage, переключатель).
- [x] S14-002: графики состояний и `mirror_status` (recharts, lazy).
- [x] S14-003: кликабельные строки, hover, бейджи.
- [x] S14-004: тесты charts/theme, документация.

### Спринт 15: Settings & Mass Migration
- [x] S15-001: `app_settings`, `SettingsService`, `GET/PATCH /settings`, маскировка токенов.
- [x] S15-002: массовая миграция `canonical_provider → gitflic` + 202 API.
- [x] S15-003: страница `/settings`, ссылка в шапке, кнопка миграции на дашборде.
- [x] S15-004: тесты и документация.

### Спринт 16: Релиз v0.3.0
- [x] S16-001: версии 0.3.0, CHANGELOG/RELEASES/README/SPEC/TODO.
- [x] S16-002: финальные проверки (`ruff`, `mypy`, `pytest`, `pnpm`).
- [x] S16-003: тег `v0.3.0`, GitHub Release, зеркало GitFlic.

**DoD:** 116 backend + 5 frontend тестов зелёные; тег `v0.3.0` в обоих провайдерах;
`SHA(main)` совпадает; Docker-сканирование работает.

---

## 6. Потенциально дальше (v0.8.0+)

| Направление | Что делать | Best practice |
|---|---|---|
| **Переезд canonical на GitFlic** | Пакетное переключение `canonical_provider` в UI после миграции | ADR-0005; массовое действие |
| **История статусов** | Таблица `status_history`; тренд «как часто репо был dirty / behind_gitflic» | SRE error budget |
| **Git SLO** | `fetch` p95 < 2 с, `status` p95 < 200 мс, `mirror_check` p95 < 5 с | Git Reliability Engineering |
| **Conflict rate** | Доля `diverged` на репозиторий; тренд | Error budget < 5% merge с конфликтами |
| **Repository health** | Размер, число объектов, packfile efficiency | GitHub Repository health |
| **Агент-режим** | DSH/OpenCode могут запрашивать статус через API | `AGENTS.md` + `/metrics` |
| **Экспорт** | CSV/JSON статусов для отчётов | Как в `ai-teacher_python` S26 |
| **Автосоздание зеркал** | `POST /mirror/create` с `confirm=true` (GitFlic import API) | Best effort, только по явному запросу |
| **Уведомления о забытых** | Триггер «репо не обновлялся N дней» | Proactive monitoring |

---

## 7. Матрица KI → спринты

| KI | Severity | Спринт закрытия | Статус |
|----|----------|-----------------|--------|
| KI-001 (fetch timeout) | Med | S7-001 | Resolved |
| KI-002 (status на больших деревьях) | Low | S7-002 | Resolved |
| KI-003 (GitHub Compare rate-limit) | Med | S7-003 | Resolved |
| KI-007 (plyer в Docker) | Med | S21-003 | Resolved |
| KI-008 (нет Conflict Manager) | Low | S21-002 | Resolved |
| KI-009 (Docker socket на Windows) | Med | S24-002 | Accepted |
| KI-010 (rate-limit PyPI/npm) | Med | S25-001, S26-002 | Resolved |
| KI-011 (OSV.dev rate-limit) | Med | S28-002 | Accepted |
| KI-012 (ложные срабатывания Secret Scanner) | Med | S28-003 | Accepted |
| KI-013 (медленный/галлюцинирующий LLM) | Med | S32-003, S33-001 | Accepted |
| KI-014 (обновление пакетов vs локальные изменения) | High | S34-001 | Accepted |

Новые KI, обнаруженные в спринтах, добавляются в `docs/KNOWN_ISSUES.md` и в эту таблицу.

---

## 8. Сквозной Definition of Done (для каждого спринта)

- [ ] Все задачи спринта `[x]` или явно перенесены в `KNOWN_ISSUES` с `KI-NNN`.
- [ ] `ruff check backend/app backend/tests` — 0.
- [ ] `mypy backend/app` — 0.
- [ ] `pytest -q` — passed (покрытие ≥ 70%).
- [ ] `pnpm --dir frontend typecheck && lint && test && build` — 0 (если трогали frontend).
- [ ] CI в GitHub зелёный.
- [ ] `docs/RELEASES.md` — отчёт по спринту (7 разделов, см. `docs/RULES.md`).
- [ ] `docs/CHANGELOG.md [Unreleased]` обновлён.
- [ ] Для релизных спринтов (S6, S12, S16) — docs-consistency audit выполнен.
- [ ] Тег создан в GitHub и GitFlic; `SHA(main)` совпадает.

---

## 9. Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Потеря документации до bootstrap | Средняя | Высокое | B-001…B-007 выполнить **сразу**, до кода |
| Приватные проекты не видны без токена | Высокая | Среднее | `GITHUB_TOKEN` с `repo`, `GITFLIC_TOKEN` с доступом; UI показывает `unavailable`, не `missing` |
| Force-push ломает зеркало | Низкая | Высокое | `history_rewritten` — критический алерт, уведомления |
| Rate-limit GitHub (60/час без токена) | Высокая | Среднее | Токен обязателен; polling замедляется при `rate_remaining < 10%` |
| Webhook не принимается локально | Высокая | Низкое | Polling — основной путь; webhook — ускорение (ADR-0006) |
| libgit2 проблемы на Windows | Средняя | Среднее | Docker как основной путь; fallback на `git --porcelain` (KI-002) |
