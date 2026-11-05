# SPEC — спецификация проекта (источник истины по контрактам)

Документ фиксирует **контракты** системы: API, схему БД, статусы, критерии приёмки.

**Версия:** v0.1.0 «Situational Awareness» · **Обновлено:** 2026-11-05

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

`summary`: `{total, clean, needs_attention, untracked, stale, errors}` (mirror-счётчики — v0.2.0).

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
```

Индексы: `repositories(path)`, `repositories(tracked)`, `repositories(github_full_name)`, `repositories(gitflic_full_name)`, `repository_status(repository_id)`, `repository_mirror_status(repository_id)`, `scan_runs(started_at)`, `webhook_events(received_at)`, `webhook_events(provider, event_type)`.

---

## 5. Технические ограничения и политика

| Параметр | Значение |
|----------|----------|
| Библиотека Git | **pygit2** для status/discovery/log/compare; shell `git` (subprocess) для fetch/rev-list |
| Fetch | `git fetch --all --prune`, таймаут 30 с; ошибка → `remote_status=unavailable` |
| Read-only | Операции чтения не изменяют рабочую директорию и индекс |
| Мутации | `pull`/`push`/`merge` — только `POST /actions` с `confirm=true` (v0.2, не реализовано в v0.1.0) |
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

## 6. Критерии приёмки v0.1.0

- [x] Сканирование находит все `.git` в заданных корнях и не уходит глубже `SCAN_DEPTH`
- [x] Для каждого репозитория определяются `modified/staged/untracked/conflicted`, `ahead/behind`, `detached`, `no_upstream`
- [x] `fetch` выполняется перед сравнением; при недоступности remote — `remote_status=unavailable`, без падения
- [x] Дашборд показывает сводку и список репозиториев с фильтром «требуют внимания»
- [x] Неучтённые репозитории отображаются отдельно и могут быть добавлены в отслеживание одним действием
- [x] Рекомендации формируются на основе состояния (`diverged` → `pull --rebase`; `ahead` → `push`)
- [x] Read-only: ни одна операция чтения не изменяет рабочую директорию
- [ ] **Mirror (v0.2.0): `mirror_status` заполняется для всех `tracked=true`; `canonical_provider` и `mirror_expected` настраиваются через PATCH; отсутствие одного из провайдеров при `mirror_expected=true` даёт `missing_on_*` и попадает в «Требуют внимания»**
- [ ] **Mirror (v0.2.0): polling + webhook; webhook инвалидирует кэш и ставит задачу на пересчёт; подпись валидируется при `WEBHOOK_SECRET`**
- [ ] **Mirror (v0.2.0): `history_rewritten` обнаруживается и поднимается как критический алерт (force-push сломал зеркало)**
- [ ] **Mirror (v0.2.0): `GET /mirror/candidates` возвращает `github_only`/`gitflic_only`/`both`/`unknown` без автоматических мутаций**
- [ ] Тесты: backend ≥ 70% покрытия, реальные временные Git-репозитории в тестах, mirror — на мок-API (response-фикстуры GitHub/GitFlic) — реальные tmp-репозитории есть, покрытие и mirror-тесты — v0.2.0
- [x] Docker Compose запускает приложение одной командой

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