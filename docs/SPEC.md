# SPEC — спецификация проекта (источник истины по контрактам)

Документ фиксирует **контракты** системы: API, схему БД, статусы, критерии приёмки.

**Версия:** v0.3.0 «Productivity & UI» · **Обновлено:** 2026-11-05

---

## 1. Область и цели

Ассистент для разработчика с множеством локальных Git-репозиториев. Требования:

| ID | Требование |
|----|------------|
| R1 | Автоматическое обнаружение Git-репозиториев в заданных корневых директориях |
| R2 | Определение локального состояния: uncommitted (modified/staged/untracked), unpushed (ahead), behind, diverged, detached HEAD, no upstream |
| R3 | Сравнение с удалённым репозиторием (GitHub/GitFlic) через fetch + compare API |
| R4 | Управляемый список отслеживаемых проектов; подсказка о неучтённых репозиториях |
| R5 | Снимок «последней выкладки»: последний коммит, ветка, статус синхронизации |
| R6 | Read-only по умолчанию; мутации (pull/push) — по явной команде с подтверждением |
| R7 | Веб-дашборд с фильтрами и детализацией |
| **R8** | **Межпровайдерная согласованность GitHub ↔ GitFlic**: обнаружение расхождений (missing / behind / diverged / history_rewritten) с учётом `canonical_provider` |
| **R9** | **Polling + webhook**: периодическая сверка и мгновенная реакция на push |

**Вне области v0.1.0:** автоматический merge/rebase, CI-интеграция, мобильное приложение, мультипользовательский режим.

---

## 2. Роли

В v0.1.0 — **один пользователь** (владелец локальной машины). Аутентификация отсутствует (bind на `127.0.0.1`). Провайдеры GitHub/GitFlic авторизуются персональными токенами (`GITHUB_TOKEN`, `GITFLIC_TOKEN`), хранятся в `.env`.

---

## 3. API (v1)

Базовый путь: `/api/v1`. Аутентификация локального API не требуется.

### 3.1. Health

| Метод | Путь | Ответ |
|-------|------|-------|
| GET | `/health` | `{status, version, git_version, scan_roots, db_ok, providers}` |

`providers.github` / `providers.gitflic`: `not_configured` в v0.1.0; реальная
проверка токенов и доступности — v0.2.0 (mirror).

### 3.2. Discovery / Сканирование

| Метод | Путь | Тело / Параметры | Ответ |
|-------|------|------------------|-------|
| POST | `/scan` | `{roots?: string[], depth?: int, force?: bool}` | `{scan_id, started_at}` (async) |
| GET | `/scan/{scan_id}` | — | `{status, found, added, skipped, errors[]}` |
| GET | `/scan/latest` | — | последний скан |
| GET | `/repositories` | `tracked?`, `skip`, `limit` | `Repository[]` |

- Глубина — `SCAN_DEPTH` (default 3); исключения — `SCAN_IGNORE` (`.venv`, `node_modules`, `vendor`, `dist`, `build`).
- Для каждого найденного `.git` создаётся/обновляется запись `Repository`; новые — `tracked=false`.
- **Неучтённые репозитории** (найденные, но не в `tracked`) возвращаются с `tracked=false` и попадают в отдельную секцию дашборда.

### 3.3. Управление списком проектов

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/repositories/{id}/track` | — | 200 `Repository` (tracked=true) |
| POST | `/repositories/{id}/untrack` | — | 200 `Repository` (tracked=false) |
| PATCH | `/repositories/{id}` | `{alias?, tags?, canonical_provider?, mirror_expected?, mirror_policy?}` | `Repository` (mirror-поля — v0.2.0) |

### 3.4. Статус репозитория (локальный)

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/repositories/{id}/status` | `fetch?: bool (default true)` | `RepositoryStatus` |
| POST | `/repositories/{id}/refresh` | `{fetch?: bool}` | `RepositoryStatus` |

`RepositoryStatus`:

```json
{
  "repository_id": 1,
  "path": "/home/user/projects/my-app",
  "branch": "main",
  "head_sha": "abc123",
  "head_subject": "feat: ...",
  "head_date": "2026-11-04T10:00:00Z",
  "upstream": "origin/main",
  "ahead": 2,
  "behind": 5,
  "state": "diverged",
  "dirty": {"modified": 3, "staged": 1, "untracked": 2, "conflicted": 0},
  "detached": false,
  "remote_status": "ok",
  "error": null,
  "checked_at": "2026-11-05T08:00:05Z"
}
```

Рекомендации отдаются отдельным эндпоинтом `/repositories/{id}/recommendations` (§3.7).

**Состояния `state` (локальные, канонические):**

| state | ahead | behind | dirty | Значение |
|-------|-------|--------|-------|----------|
| `current` | 0 | 0 | false | Полностью синхронизирован |
| `behind` | 0 | >0 | — | Удалённый имеет новые коммиты |
| `ahead` | >0 | 0 | — | Есть незапушенные коммиты |
| `diverged` | >0 | >0 | — | Обе стороны имеют новые коммиты |
| `dirty` | — | — | true | Есть незакоммиченные изменения |
| `no_upstream` | — | — | — | Нет tracking-ветки |
| `detached` | — | — | — | Detached HEAD |
| `error` | — | — | — | Ошибка доступа к репозиторию/remote |

### 3.5. Сравнение с удалённым (remote compare, в пределах провайдера)

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/repositories/{id}/compare` | `base?` (default: upstream), `head?` (default: HEAD) | `{ahead, behind, status, commits[]}` |
| GET | `/repositories/{id}/log` | `limit` (default 20) | `[{sha, subject, author, date}]` |

`fetch` обязателен перед сравнением; при ошибке — `remote_status=unavailable`, `ahead/behind` считаются по локальным `refs/remotes/*` (пометка `stale`).

### 3.6. Сводка / Dashboard

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/dashboard` | `tracked_only?` | `{summary, repositories[]}` |

`summary`: `{total, clean, needs_attention, untracked, stale, errors, mirror_issues, by_state, by_mirror_status}` (mirror-счётчики — v0.2.0).

**Секция «Не отслеживаются»** — `tracked=false`. **Секция «Зеркала»** — `mirror_status != in_sync | not_applicable`, см. §3.8.

### 3.7. Рекомендации (action queue)

| Метод | Путь | Ответ |
|-------|------|-------|
| GET | `/repositories/{id}/recommendations` | `[{action, reason, command, category}]` |

`category ∈ {local, mirror}` — рекомендации по локальному состоянию и по зеркалам разделены. Рекомендации **не выполняются автоматически**.

### 3.8. Mirror / межпровайдерная согласованность (GitHub ↔ GitFlic) — R8/R9
**Назначение.** Отдельный сервис (`MirrorService`) ходит в API GitHub и API GitFlic, сравнивает `HEAD SHA` default-ветки и возвращает канонический `mirror_status`. Сравнение **не** опирается на локальный клон: он может знать только один remote.

**Статус реализации (v0.2.0, Sprint 9):** эндпоинты §3.8.1, все 9 значений `mirror_status`, polling и webhooks реализованы. Классификация при разных SHA использует детерминированную эвристику по датам коммитов (`sha+date-heuristic`); полноценный provider Compare API — v0.3.

**Политика.** У каждого репозитория есть `canonical_provider` (`github | gitflic | both`) и `mirror_expected` (bool). Настраивается пользователем. **Default — `github`, `mirror_expected=true`** (этап миграции в GitFlic), позже — переключение на `gitflic` по мере переезда. Для осознанно односторонних проектов — `mirror_expected=false` (шума не будет).

#### 3.8.1. Эндпоинты

| Метод | Путь | Параметры / тело | Ответ |
|-------|------|------------------|-------|
| GET | `/repositories/{id}/mirror` | `refresh?: bool (default false)` | `MirrorStatus` |
| GET | `/repositories/{id}/ci-status` | — | `{branch, github, gitflic, aggregate}` |
| POST | `/repositories/{id}/mirror/refresh` | — | `MirrorStatus` (принудительный пересчёт) |
| GET | `/mirror/candidates` | `provider?` | `{github_only[], gitflic_only[], both[], unknown[]}` |
| PATCH | `/repositories/{id}/mirror-policy` | `{canonical_provider?, mirror_expected?, mirror_policy?}` | `Repository` |
| POST | `/webhooks/gitflic` | (payload от GitFlic) | 202 — принимает событие push/branch, инвалидирует кэш `MirrorStatus` для соответствующих репозиториев |
| POST | `/webhooks/github` | (payload от GitHub) | 202 — аналогично |
| POST | `/mirror/poll` | `{force?: bool}` | `{checked, updated, errors[]}` — принудительный прогон polling'а (для cron/ручного) |

#### 3.8.2. `MirrorStatus`

```json
{
  "repository_id": 1,
  "github": {
    "full_name": "iilmchat/iiruchating",
    "branch": "main",
    "head_sha": "abc123",
    "head_date": "2026-11-04T10:00:00Z",
    "private": true,
    "checked_at": "2026-11-05T08:00:00Z"
  },
  "gitflic": {
    "full_name": "ruchating/iiruchating",
    "branch": "main",
    "head_sha": "def456",
    "head_date": "2026-11-03T12:00:00Z",
    "private": true,
    "checked_at": "2026-11-05T08:00:00Z"
  },
  "mirror_status": "behind_gitflic",
  "canonical_provider": "github",
  "mirror_expected": true,
  "recommendations": [
    {"action": "push-mirror", "reason": "GitFlic отстаёт на 2 коммита",
     "command": "git push gitflic main", "category": "mirror"}
  ],
  "checked_at": "2026-11-05T08:00:05Z"
}
```

#### 3.8.3. Канонические значения `mirror_status`

| mirror_status | Условие | Попадает в «Требуют внимания»? |
|---------------|---------|-------------------------------|
| `in_sync` | SHA совпадают | Нет |
| `missing_on_gitflic` | Есть только в GitHub | Да, если `mirror_expected=true` |
| `missing_on_github` | Есть только в GitFlic | Да, если `mirror_expected=true` |
| `behind_gitflic` | `canonical=github`, SHA у GitFlic старее | Да, если `mirror_expected=true` |
| `behind_github` | `canonical=gitflic`, SHA у GitHub старее | Да, если `mirror_expected=true` |
| `diverged` | SHA разные, но история не переписана (по датам/родителям) | Да (warning) |
| `history_rewritten` | SHA разные и один не является предком другого в зеркале | **Да, критический алерт** |
| `not_applicable` | `mirror_expected=false` | Нет |
| `unavailable` | Один из провайдеров недоступен (нет токена, rate limit, 5xx) | Нет (stale, отдельный счётчик) |

#### 3.8.4. Polling + webhook (R9)

- **Polling:** фоновый шедулер (asyncio-задача в `lifespan`) с интервалом `MIRROR_POLL_INTERVAL_SECONDS` (default **300** — 5 мин) пересчитывает `MirrorStatus` для всех `tracked=true` с `mirror_expected=true`.
- **Webhook:** `POST /webhooks/gitflic` и `POST /webhooks/github` принимают события `push` / `branch_update`, инвалидируют кэш для соответствующего репозитория, ставят задачу на внеочередной пересчёт (без блокировки ответа). Подпись webhook (HMAC) валидируется, если `WEBHOOK_SECRET` задан.
- **Кэш:** `MIRROR_STATUS_TTL_SECONDS` (default **300**) — дашборд не ходит в два API на каждый запрос. Refresh через `POST /mirror/refresh` — обходит кэш.
- **Fail-open:** при недоступном GitHub или GitFlic API — `mirror_status=unavailable`, остальные поля заполняются насколько возможно; UI показывает «проверено N минут назад».

#### 3.8.5. Обнаружение кандидатов

`GET /mirror/candidates` сравнивает **списки репозиториев** провайдеров (не диска):

- `github_only` — есть в GitHub (`GET /user/repos` или `GET /orgs/{org}/repos`), нет в GitFlic.
- `gitflic_only` — наоборот.
- `both` — есть в обоих.
- `unknown` — не удалось получить (нет токена/ошибка API).

Каждый элемент: `{provider, full_name, private, url, canonical_provider_guess, suggested_action}`. **Никаких автоматических мутаций** — только кандидаты для ручного решения (создать зеркало / отметить `mirror_expected=false`).

#### 3.8.6. Rate limits и стратегия запросов
| Провайдер | Лимит (authenticated) | Стратегия |
|-----------|----------------------|-----------|
| GitHub | 5000 req/час | Однократный `GET /repos/{o}/{r}/branches/{b}` на репозиторий, кэш 300 с |
| GitFlic | (по докам провайдера) | Однократный `GET /project/{alias}/{project}/commit` / `list_commits`, кэш 300 с |

Если `rate_remaining < 10%` — polling автоматически замедляется (`MIRROR_POLL_INTERVAL_SECONDS * 2`) до восстановления лимита; при 403/429 — `unavailable` + warning в лог, без падения.

---

## 3.9. Actions — явные мутации (v0.2.0, ADR-0003)

Автоматических мутаций нет: действие выполняется только при `confirm=true` и
всегда попадает в `action_log`.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/repositories/{id}/actions/{action}` | `{confirm: true}` | `ActionLog` |
| POST | `/mirror/actions/{action}` | `{confirm: true, repository_id}` | `ActionLog` |
| GET | `/admin/actions` | `repository_id?`, `limit?` | `ActionLog[]` |

- `action ∈ {pull, push, stash}`; `mirror action = push-mirror`.
- Без `confirm=true` → 400; неизвестное действие → 400.
- Destructive-команды (`reset --hard`, `clean -f`, `push --force`, `checkout .`) отсутствуют.
- `ActionLog`: `repository_id, action, command, status, exit_code, output, actor, created_at`.

---

## 3.10. Метрики (Prometheus)

| Метод | Путь | Ответ |
|-------|------|-------|
| GET | `/metrics` | Prometheus text format (`text/plain; version=0.0.4`) |

Метрики: `iiruchating_fetch_duration_seconds`, `iiruchating_status_duration_seconds`,
`iiruchating_repositories_total{state}`, `iiruchating_scan_duration_seconds`,
`iiruchating_mirror_status_total{status}`, `iiruchating_mirror_check_duration_seconds`.
Эндпоинт local-only, без авторизации (как `/health`).

---

## 3.11. Bulk actions

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| POST | `/repositories/actions/fetch_all` | `tracked_only?` (default true), body `{repo_ids?}` | `202 {status:"accepted"}` |
| POST | `/repositories/actions/sync_mirrors_all` | `tracked_only?`, body `{repo_ids?}` | `202 {status:"accepted"}` |
| POST | `/repositories/actions/migrate_to_gitflic` | — | `202 {status:"accepted"}` |

Задачи выполняются в `BackgroundTasks` с ограничением concurrency (5).
`repo_ids` (опционально) ограничивает операцию выбранными репозиториями; без него
действует фильтр `tracked_only`.
`fetch_all` делает `git fetch --all --prune`; `sync_mirrors_all` — `git push gitflic <branch>`
для `mirror_status ∈ {behind_gitflic, missing_on_gitflic}` и пишет `action_log` (`actor=bulk`).
`migrate_to_gitflic` переводит `canonical_provider=github` на `gitflic` при заданном
`gitflic_full_name`, меняет `mirror_policy` и пишет отчёт `{updated, skipped, total}` в лог.

---

## 3.12. Settings

| Метод | Путь | Тело / Ответ |
|-------|------|--------------|
| GET | `/settings` | `{scan_roots, github_token, gitflic_token, webhook_secret, default_canonical_provider}` |
| PATCH | `/settings` | те же поля (все опциональны) → обновлённые значения |

Токены и `webhook_secret` в ответе **маскируются** (`ghp_****1234`).
Разрешённые ключи: `scan_roots`, `github_token`, `gitflic_token`, `webhook_secret`,
`default_canonical_provider`. Значения хранятся в `app_settings`; при старте
подхватываются в конфиг (fallback — `config.py`).

---

## 4. Схема БД (SQLite / PostgreSQL)
```
repositories(
  id, path*, alias, tracked BOOLEAN DEFAULT false,
  remote_url, provider (github|gitflic|other),
  -- mirror (R8):
  github_full_name   TEXT NULL,             -- "owner/repo"
  gitflic_full_name  TEXT NULL,             -- "userAlias/projectAlias"
  canonical_provider TEXT DEFAULT 'github', -- github | gitflic | both
  mirror_expected    BOOLEAN DEFAULT true,
  mirror_policy      TEXT DEFAULT 'github_to_gitflic',
  last_seen_at, created_at, updated_at,
  tags JSONB
)

repository_status(
  id, repository_id→repositories UNIQUE,
  branch, head_sha, head_subject, head_date,
  upstream, ahead, behind, state,
  dirty_modified, dirty_staged, dirty_untracked, dirty_conflicted,
  stash_count, detached BOOLEAN,
  remote_status, recommendations JSONB,
  checked_at
)

repository_mirror_status(   -- NEW (R8)
  id, repository_id→repositories UNIQUE,
  github_head_sha, gitflic_head_sha,
  github_branch,   gitflic_branch,
  github_checked_at, gitflic_checked_at,
  mirror_status TEXT,
  details JSONB,          -- {dates, parents, private flags, rate_remaining, ...}
  checked_at
)

scan_runs(
  id, started_at, finished_at, status,
  roots JSONB, depth, found_count, added_count, skipped_count, errors JSONB
)

webhook_events(             -- NEW (R9)
  id, provider (github|gitflic), event_type,
  repository_id→repositories NULL,
  payload JSONB, received_at, processed_at, status
)

action_log(                 -- S10-005
  id, repository_id→repositories NULL, action, command, status,
  output, error, duration_ms, exit_code, actor, created_at
)

app_settings(               -- S15-001
  key* TEXT PRIMARY KEY, value TEXT NULL, updated_at
)
```

Индексы: `repositories(path)`, `repositories(tracked)`, `repositories(github_full_name)`, `repositories(gitflic_full_name)`, `repository_status(repository_id)`, `repository_mirror_status(repository_id)`, `scan_runs(started_at)`, `webhook_events(received_at)`, `webhook_events(provider, event_type)`.

---

## 5. Технические ограничения и политика

| Параметр | Значение |
|----------|----------|
| Библиотека Git | **pygit2** для status/discovery/log/compare; shell `git` (subprocess) для fetch/rev-list |
| Fetch | `git fetch --all --prune`, таймаут 30 с; ошибка → `remote_status=unavailable` |
| Read-only | Операции чтения не изменяют рабочую директорию и индекс |
| Мутации | `fetch`/`pull`/`push`/`stash`/`push_mirror` — только `POST .../actions/{action}` с `confirm=true` и аудитом `action_log` (v0.2.0) |
| Глубина сканирования | `SCAN_DEPTH` (default 3) |
| Исключения сканирования | `.git`, `node_modules`, `.venv`, `vendor`, `dist`, `build`, `target` |
| Параллелизм сканирования | `SCAN_CONCURRENCY` (default 4) |
| Кэш локального статуса | `STATUS_TTL_SECONDS` (default 60) |
| **Кэш compare** | **`COMPARE_TTL_SECONDS` (default 60; ключ `repo_id, base, head`)** |
| **Кэш mirror-статуса** | **`MIRROR_STATUS_TTL_SECONDS` (default 300)** |
| **Интервал polling** | **`MIRROR_POLL_INTERVAL_SECONDS` (default 300; замедление при rate-limit)** |
| **Webhook secret** | **`WEBHOOK_SECRET` (опционально, HMAC-валидация)** |
| **Токены провайдеров** | **`GITHUB_TOKEN`, `GITFLIC_TOKEN` (обязательны для mirror; без них `mirror_status=unavailable`, `mirror_expected` не влияет на UI-шум)** |

---

## 6. Критерии приёмки v0.3.0

- [x] Сканирование находит все `.git` в заданных корнях и не уходит глубже `SCAN_DEPTH`
- [x] Для каждого репозитория определяются `modified/staged/untracked/conflicted`, `ahead/behind`, `detached`, `no_upstream`
- [x] `fetch` выполняется перед сравнением; при недоступности remote — `remote_status=unavailable`, без падения
- [x] Дашборд показывает сводку и список репозиториев с фильтром «требуют внимания»
- [x] Неучтённые репозитории отображаются отдельно и могут быть добавлены в отслеживание одним действием
- [x] Рекомендации формируются на основе состояния (`diverged` → `pull --rebase`; `ahead` → `push`)
- [x] Read-only: ни одна операция чтения не изменяет рабочую директорию
- [x] **Mirror: `mirror_status` заполняется для всех `tracked=true`; `canonical_provider` и `mirror_expected` настраиваются через PATCH; отсутствие одного из провайдеров при `mirror_expected=true` даёт `missing_on_*` и попадает в «Требуют внимания»**
- [x] **Mirror: polling + webhook; webhook инвалидирует кэш и ставит задачу на пересчёт; подпись валидируется при `WEBHOOK_SECRET`**
- [x] **Mirror: `history_rewritten` обнаруживается и поднимается как критический алерт (force-push сломал зеркало)**
- [x] **Mirror: `GET /mirror/candidates` возвращает `github_only`/`gitflic_only`/`both`/`unknown` без автоматических мутаций**
- [x] Тесты: реальные временные Git-репозитории в тестах; mirror/CI — на фейковых клиентах; покрытие — ориентир ≥ 70%
- [x] Docker Compose запускает приложение одной командой
- [x] **Actions: мутации только с `confirm=true`, аудит `action_log`**
- [x] **CI status и desktop-уведомления реализованы (v0.2.0)**
- [x] **Bulk: массовые fetch/sync/migrate с ограничением concurrency и фоновыми API (v0.3.0)**
- [x] **Settings: хранение в БД, маскировка токенов, применение без перезапуска (v0.3.0)**
- [x] **UI: тёмная тема, графики состояний/зеркал, поиск и сортировка (v0.3.0)**

---

## 7. Совместимость и версии

| Компонент | Версия |
|-----------|--------|
| Python | 3.12 |
| FastAPI / Pydantic | 0.115+ / 2.10+ |
| pygit2 | 1.15+ (libgit2) |
| git CLI | 2.40+ (fetch/rev-list) |
| GitHub REST API | v3 (2022-11-28) — v0.2.0 |
| GitFlic REST API | актуальная (см. docs.gitflic.ru) — v0.2.0 |
| SQLite / PostgreSQL | 3.45+ / 17 |
| React / Vite / TypeScript | 19 / 8 / 7 |

---

## 8. Roadmap

| Версия | Фокус | Документ |
|--------|-------|----------|
| v0.4.0 | UX/UI, advanced table, saved views, command palette, a11y, Telegram, heatmap, export | `TODO_V0.4.md` |
| v0.5.0+ | серверная синхронизация представлений, история статусов, расширенные интеграции | `TODO.md` |

---

## 9. UX/UI Guidelines

### 9.1 Таблица репозиториев

- Колонки: выбор, имя/путь, ветка, локальный статус, зеркало, ahead/behind, действия.
- **Batch selection:** чекбокс в строке и «выбрать все» в пределах активного фильтра;
  массовые операции (`fetch_all`, `sync_mirrors_all`) принимают `repository_ids` и без
  выбора работают по текущей семантике «все tracked».
- **Управление колонками:** видимость, порядок (drag-and-drop), ширина (resize);
  состояние сохраняется в `localStorage` (`table.columns.v1`) и переживает reload.
- **Терминальный стиль:** SHA, пути и команды — `font-mono`; числовые колонки
  выровнены вправо; длинные пути обрезаются с tooltip.
- Строка кликабельна (мышь + `Enter`), действия внутри строки не триггерят переход.
- Контекстное меню по `right-click`/`Shift+F10`: Fetch, Push, Copy path, Copy SHA,
  «Открыть детали»; мутации — через подтверждение (`confirm=true`).

### 9.2 Фильтры и сохранённые представления

- Фильтры представлены чипами: статус, canonical provider, `mirror_status`,
  tracked, stale; активные чипы видны всегда, есть «Очистить всё».
- **Saved view** = `{name, filters, sort, visible_columns, column_order, widths}`.
- Версионированная схема (`version: 1`); несовместимые версии мигрируются или
  сбрасываются с уведомлением. v0.4.0 — localStorage; v0.5.0 — опциональная БД.
- Активное представление и фильтры отражаются в query string (shareable URL).

### 9.3 Command Palette и клавиатура

| Комбинация | Действие |
|------------|----------|
| `Ctrl/Cmd+K` | Открыть Command Palette (репозитории, действия, страницы) |
| `↑` / `↓` | Перемещение по таблице или результатам палитры |
| `Enter` | Открыть выбранное / выполнить команду |
| `Esc` | Закрыть модалку/палитру, снять фокус |
| `/` | Фокус в поиск |
| `Space` | Выбрать строку (batch selection) |
| `Shift+F10` | Контекстное меню строки |
| `?` | Панель подсказок по горячим клавишам |

Палитра не перехватывает ввод, когда фокус в `input`/`textarea`/`select`.

### 9.4 Доступность (A11y)

- Цвет — не единственный носитель смысла: у бейджей есть иконка/форма
  (`✓ current`, `! dirty`, `↓ behind`, `⚠ diverged`, `? no_upstream`).
- Контраст текста и фона — не ниже WCAG AA (4.5:1); тёмная тема проверяется отдельно.
- Видимый `focus-visible` у всех интерактивных элементов; логичный порядок Tab.
- `aria-label`/`aria-describedby` для иконочных кнопок и модалок; `role="dialog"`,
  `aria-modal`, возврат фокуса после закрытия.
- Анимации уважают `prefers-reduced-motion`.

### 9.5 Stale data

- `checked_at` старше TTL или `remote_status ∈ {stale, unavailable}` → блок
  приглушается (opacity) и получает бейдж «Устарело» с tooltip «обновлено N минут назад».
- Stale-статус не скрывает данные и не блокирует действия.

### 9.6 Conflict Manager

- Для `state="diverged"` показывается список unmerged-файлов:
  `git diff --name-only --diff-filter=U` (read-only).
- Файлы только отображаются; автоматическое разрешение конфликтов не выполняется.

### 9.7 Export

- Экспорт текущего среза таблицы в CSV/JSON формируется на клиенте из загруженных
  данных (без дополнительных серверных отчётов); экспорт уважает фильтры и видимые колонки.