# SPEC — спецификация проекта (источник истины по контрактам)

Документ фиксирует **контракты** системы: API, схему БД, статусы, критерии приёмки.
Docker §3.14 реализован в Sprint 24; dependency §3.15 (Python/Node) — в Sprint 25–26;
Security §3.16 — в Sprint 28; Insights §3.17 — в Sprint 29.
AI §3.18 (commit message — Sprint 32, CVE explain — Sprint 33), global
analytics §3.19 и dependency updates §3.20 — реализованы в Sprint 32–34.
§3.26 (RAG-поиск по коду) и §3.27 (GigaChat OAuth) реализованы в v0.9.0
(Sprints 43–44). §3.28 (single-user auth) — реализовано в v1.0.0 (Sprint 47);
§3.29 (AI Code Review, Conflict Resolver, Release Notes) — реализовано в
Sprints 53–54; §3.30 (conversational RAG) — реализовано в Sprint 55;
см. [`TODO_V1.2.0.md`](../TODO_V1.2.0.md). §3.31–§3.33 (Team Edition, SAST,
автоматические PR) — реализованы в v1.3.0 (Sprints 57–59), см.
[`TODO_V1.3.0.md`](../TODO_V1.3.0.md). v1.4.0–v1.4.1 — SQLite + `sqlite-vec`
RAG и управление паролями (Sprint 61); v1.4.2 — разделение `model_name` (чат) и
`embedding_model` (RAG), миграция 016. §3.34 (Global Tech Debt Dashboard) и
§3.35 (IaC Scanning) — **план v1.5.0** (Sprints 63–64), см.
[`TODO_V1.5.0.md`](../TODO_V1.5.0.md).

**Версия:** v1.4.2 (текущая) · v1.5.0 (планирование) · **Обновлено:** 2026-11-11

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
| **R10** | **Supply-chain security (v0.6.0): CVE-проверка зависимостей через OSV.dev и базовый поиск секретов — без изменения репозитория** |
| **R11** | **Insights (v0.6.0): hotspots по churn и commit frequency (DORA-lite) из Git-истории** |
| **R12** | **AI (v0.7.0): локальный LLM через OpenAI-совместимый API — черновик commit message и объяснение CVE без автоматических мутаций** |
| **R13** | **Global analytics (v0.7.0): сводка версий популярных пакетов по всем tracked-репозиториям и кандидаты на унификацию** |
| **R14** | **Dependency updates (v0.7.0): обновление пакетов только по явному подтверждению, на чистом worktree и с аудитом `action_log`** |
| **R15** | **E2E и bundle budget (v0.9.0): 3 критических сценария Playwright; entry bundle < 90 kB gzip** |
| **R16** | **GigaChat OAuth и smart cache (v0.9.0): нативный OAuth 2.0 adapter и отказ от вызова LLM при неизменном состоянии** |
| **R17** | **RAG-поиск по коду (v0.9.0): индексация README/docs/src в pgvector и семантический поиск без изменения репозиториев** |
| **R18** | **Single-user auth (v1.0.0): защита API при доступе по LAN через bcrypt-пароль, JWT и httpOnly cookie; один пользователь без RBAC** |
| **R19** | **Desktop app (v1.0.0, план): Tauri-обёртка с автоматическим запуском Python-sidecar; Docker остаётся серверной опцией** |
| **R20** | **Global Tech Debt Dashboard (v1.5.0, план): агрегированная статистика outdated-пакетов, CVE, dirty-файлов и diverged-веток по всем tracked-репозиториям + AI-отчёт по всей кодовой базе** |
| **R21** | **IaC Scanning (v1.5.0, план): read-only аудит `Dockerfile` и `docker-compose.yml` без запуска Docker, сборки образов и сетевых вызовов** |
| **R22** | **Global IaC summary (v1.5.0, план): сводка инфраструктурных проблем по всем tracked-репозиториям на дашборде** |

**Вне области v0.1.0:** автоматический merge/rebase, CI-интеграция, мобильное приложение, мультипользовательский режим.

---

## 2. Роли

В v0.9.0 — **один пользователь** (владелец локальной машины). Аутентификация
отсутствует при bind на `127.0.0.1`; при доступе по LAN включается single-user
auth (v1.0.0, §3.28). Провайдеры GitHub/GitFlic авторизуются персональными
токенами (`GITHUB_TOKEN`, `GITFLIC_TOKEN`), хранятся в `.env`. LLM API key (если
нужен) хранится в `app_settings`, маскируется в API и не экспортируется.

**v1.0.0 (Sprint 47 — реализовано):** без регистрации и RBAC. Пользователь
создаётся bootstrap-ом из `.env`; пароль хранится только как bcrypt-hash; JWT
выдаётся на 7 дней. Подробности — §3.28 и [`TODO_V1.0.md`](../TODO_V1.0.md).

---

## 3. API (v1)

Базовый путь: `/api/v1`. В v0.9.0 аутентификация локального API не требуется.
В v1.0.0 (план) все роуты, кроме `/health`, `/metrics` и `/auth/login`,
требуют JWT (cookie или `Authorization: Bearer`); см. §3.28.

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

`repositories[]` включает последний `status`, `mirror` и `ci` (`{github, gitflic, aggregate}`);
CI-статусы кэшируются (60 с) и не блокируют загрузку дашборда.

`summary`: `{total, clean, needs_attention, untracked, stale, errors, mirror_issues, by_state, by_mirror_status}` (mirror-счётчики — v0.2.0).

**Секция «Не отслеживаются»** — `tracked=false`. **Секция «Зеркала»** — `mirror_status != in_sync | not_applicable`, см. §3.8.

**v1.5.0 (план):** сводный технический долг по всем tracked-репозиториям
отдаётся отдельным эндпоинтом `GET /dashboard/global-stats` (§3.34) и **не**
утяжеляет `GET /dashboard`; IaC-сводка — `GET /dashboard/global-iac` (§3.35).

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

### 3.9. Actions — явные мутации (v0.2.0, ADR-0003)

Автоматических мутаций нет: действие выполняется только при `confirm=true` и
всегда попадает в `action_log`.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/repositories/{id}/actions/{action}` | `{confirm: true}` | `ActionLog` |
| POST | `/repositories/{id}/actions/commit` | `{confirm: true, message}` | `ActionLog` (v0.7.0) |
| POST | `/repositories/{id}/actions/update-dependencies` | `{confirm: true, ecosystem: python\|node}` | `ActionLog` (v0.7.0) |
| POST | `/mirror/actions/{action}` | `{confirm: true, repository_id}` | `ActionLog` |
| GET | `/admin/actions` | `repository_id?`, `limit?` | `ActionLog[]` |

- `action ∈ {pull, push, stash}`; `mirror action = push-mirror`.
- `commit` (v0.7.0) выполняется только с `confirm=true` и непустым `message`
  (≤ 2000 символов); без сообщения → 400. Аудит — `action_log`
  (`action="commit"`), автоматического коммита из AI-модалки нет.
- Без `confirm=true` → 400; неизвестное действие → 400.
- `update-dependencies` (v0.7.0) — отдельное действие Sprint 34; требует чистого
  worktree (`409 "Worktree must be clean"`), пишет `action_log` даже при
  отказе/ошибке. Детали — §3.20.
- Destructive-команды (`reset --hard`, `clean -f`, `push --force`, `checkout .`) отсутствуют.
- `ActionLog`: `repository_id, action, command, status, exit_code, output, actor, created_at`.

---

### 3.10. Метрики (Prometheus)

| Метод | Путь | Ответ |
|-------|------|-------|
| GET | `/metrics` | Prometheus text format (`text/plain; version=0.0.4`) |

Метрики: `iiruchating_fetch_duration_seconds`, `iiruchating_status_duration_seconds`,
`iiruchating_repositories_total{state}`, `iiruchating_scan_duration_seconds`,
`iiruchating_mirror_status_total{status}`, `iiruchating_mirror_check_duration_seconds`.
Эндпоинт local-only, без авторизации (как `/health`).

---

### 3.11. Bulk actions

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| POST | `/repositories/actions/fetch_all` | `tracked_only?` (default true), body `{repo_ids?}` | `202 {status:"accepted"}` |
| POST | `/repositories/actions/sync_mirrors_all` | `tracked_only?`, body `{repo_ids?}` | `202 {status:"accepted"}` |
| POST | `/repositories/actions/migrate_to_gitflic` | — | `202 {status:"accepted"}` |
| POST | `/repositories/actions/update_dependencies_all` | `{confirm:true, ecosystem: python\|node, repo_ids?: int[]}` | `202 {status:"accepted"}` (v0.7.0) |

Задачи выполняются в `BackgroundTasks` с ограничением concurrency (5).
`repo_ids` (опционально) ограничивает операцию выбранными репозиториями; без него
действует фильтр `tracked_only`.
`fetch_all` делает `git fetch --all --prune`; `sync_mirrors_all` — `git push gitflic <branch>`
для `mirror_status ∈ {behind_gitflic, missing_on_gitflic}` и пишет `action_log` (`actor=bulk`).
`migrate_to_gitflic` переводит `canonical_provider=github` на `gitflic` при заданном
`gitflic_full_name`, меняет `mirror_policy` и пишет отчёт `{updated, skipped, total}` в лог.
`update_dependencies_all` (v0.7.0) запускает §3.20 для выбранных `repo_ids`
(или всех tracked) с concurrency 1–2; грязные репозитории пропускаются с
`ActionLog.status=error`, `actor=bulk`.

---

### 3.12. Settings

| Метод | Путь | Тело / Ответ |
|-------|------|--------------|
| GET | `/settings` | `{scan_roots, github_token, gitflic_token, webhook_secret, default_canonical_provider, llm_enabled, llm_base_url, llm_model, llm_api_key, llm_timeout_seconds, llm_max_diff_chars, llm_allow_remote, telegram_bot_token, telegram_chat_id, notifications_enabled, fetch_timeout, status_ttl_seconds, mirror_poll_interval_seconds}` |
| PATCH | `/settings` | те же поля (все опциональны) → обновлённые значения |
| GET | `/settings/status` | `{is_configured: bool}` — `true`, если `SCAN_ROOTS` непустой (v1.1.0, S50) |

Токены, `webhook_secret`, `llm_api_key` и `telegram_bot_token` в ответе
**маскируются** (`ghp_****1234`, `sk-****1234`). Разрешённые ключи: `scan_roots`,
`github_token`, `gitflic_token`, `webhook_secret`, `default_canonical_provider`,
`llm_enabled`, `llm_base_url`, `llm_model`, `llm_api_key`,
`llm_timeout_seconds`, `llm_max_diff_chars`, `llm_allow_remote`,
`telegram_bot_token`, `telegram_chat_id`, `notifications_enabled`,
`fetch_timeout`, `status_ttl_seconds`, `mirror_poll_interval_seconds`. Значения
хранятся в `app_settings`; при старте подхватываются в конфиг
(fallback — `config.py`). Если таблица `app_settings` пуста, при старте она
**сидируется** значениями из `.env`/`config.py` (S43-001), поэтому все
параметры видны и редактируются в UI без ручного PATCH.

**Группы UI:** «Уведомления» (`telegram_bot_token`, `telegram_chat_id`,
`notifications_enabled`) и «Производительность» (`fetch_timeout`,
`status_ttl_seconds`, `mirror_poll_interval_seconds`). Изменения применяются к
`NotificationService`, `RemoteService`, `StatusService` и `MirrorScheduler`
без перезапуска.

**LLM-настройки (v0.7.0, Sprint 32 — реализовано):**

- `llm_enabled` (default **false**) — AI-функции выключены до явного включения.
- `llm_base_url` (default `http://127.0.0.1:1234/v1`) — LM Studio; Ollama —
  `http://127.0.0.1:11434/v1`.
- `llm_model` (default `qwen2.5-coder-7b-instruct`).
- `llm_api_key` — опционально; для локальных серверов обычно пустой.
- `llm_timeout_seconds` (default 30).
- `llm_max_diff_chars` (default 10000) — лимит diff для генерации коммита.
- `llm_allow_remote` (default **false**) — не-loopback endpoint запрещён, пока
  пользователь явно не разрешит.
- Пустое поле `llm_api_key` при PATCH означает «не менять».

---

### 3.13. Conflicts, activity & export

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/repositories/{id}/conflicts` | — | `{repository_id, files[]}` (unmerged, read-only) |
| GET | `/dashboard/heatmap` | `days?` (default 365) | `{"YYYY-MM-DD": commits}` |
| GET | `/repositories/export` | `format=csv|json` | файл (attachment) |

`conflicts` использует `git diff --name-only --diff-filter=U` (без изменений в репозитории).
`heatmap` агрегирует `git log --since` по всем `tracked` репозиториям.
`export` отдаёт все репозитории со статусом/зеркалом; CSV или JSON.

---

### 3.14. Docker-интеграция (v0.5.0, Sprint 24)

Read-only срез runtime-состояния проекта. Эндпоинт **не управляет** контейнерами:
Docker SDK вызывает только `ping()` и `containers.list(all=True)`.

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/repositories/{id}/docker` | `refresh?: bool (default false)` | `DockerStatus` |

`DockerStatus`:

```json
{
  "repository_id": 1,
  "status": "running",
  "containers": [
    {
      "id": "3f2a1b4c9d10",
      "name": "app-web-1",
      "image": "nginx:latest",
      "state": "running",
      "status": "running (healthy)",
      "health": "healthy",
      "ports": [
        {"host_ip": "0.0.0.0", "host_port": 8080, "container_port": 80, "protocol": "tcp"}
      ],
      "compose_project": "app",
      "compose_service": "web",
      "match": "mount_source"
    }
  ],
  "error": null,
  "checked_at": "2026-11-06T10:00:00Z"
}
```

**Поля:**

- `status ∈ {running, stopped, not_found, unavailable}`:
  - `running` — хотя бы один найденный контейнер в состоянии `running`/`restarting`;
  - `stopped` — контейнеры найдены, но ни один не running;
  - `not_found` — Docker доступен, но совпадений с репозиторием нет;
  - `unavailable` — Docker отключён, демон недоступен или произошла ошибка.
- `containers[]` — только контейнеры, сопоставленные с репозиторием.
- `state` — состояние Docker (`running`, `exited`, `created`, `paused`,
  `restarting`, `dead`, `removing`).
- `status` — человекочитаемая строка состояния; при наличии healthcheck
  содержит `(<health>)`.
- `health ∈ {healthy, unhealthy, starting, null}`; `null` — healthcheck отсутствует.
- `ports[]` — порты контейнера. `host_port=null` означает, что порт не опубликован
  на хосте.
- `compose_project` / `compose_service` — значения labels Docker Compose (или `null`).
- `match ∈ {mount_source, mount_destination, compose_workdir, compose_project,
  name, image}` — правило, по которому контейнер сопоставлен с репозиторием.
- `error` — строка причины для `unavailable`; иначе `null`. Типовые значения:
  `Docker daemon not running`, `Docker daemon permission denied`,
  `Docker integration is disabled`.

**Сопоставление repository ↔ containers:**

1. bind-mount `Source` == `repository.path` после нормализации путей и применения
   `DOCKER_PATH_MAP` (host→container, например `C:/Projects=/projects`);
2. bind-mount `Destination` == `repository.path` (после того же маппинга);
3. label `com.docker.compose.project.working_dir` == `repository.path`;
4. label `com.docker.compose.project` == slug имени каталога репозитория;
5. имя контейнера или имя образа содержит slug.

Если path mapping не задан и пути находятся в разных namespace (backend в
контейнере, проект на хосте), path-сравнение пропускается; используются
compose project/имя. Named volumes не считаются bind-mount'ом репозитория.

Несколько контейнеров одного compose-проекта возвращаются все; при отсутствии
совпадений — `status=not_found`, `containers=[]`, `error=null`.

**Кэш и ошибки:** `DOCKER_STATUS_TTL_SECONDS` (default 30); `refresh=true`
обходит кэш. `DockerException` и ошибки соединения **не** дают 5xx:
`status=unavailable`, `error` заполнен, HTTP 200. `checked_at` — момент
формирования ответа; при отдаче из кэша данные могут быть не новее TTL.

**Ограничения:** start/stop/restart/pause/exec/logs отсутствуют; сырой JSON
Docker API наружу не отдаётся, только нормализованная схема выше.

---

### 3.15. Dependency management (v0.5.0, Sprint 25–26; .NET — v1.3.0, Sprint 57)

Проверка объявленных зависимостей по манифестам в корне и вложенных
каталогах репозитория (`backend/requirements.txt`, `frontend/package.json`,
`*.csproj`, `Directory.Packages.props`).
Файлы только читаются; в рамках проверки зависимостей `pip`/`npm`/`pnpm`/
`dotnet` не запускаются (обновление пакетов — отдельное действие §3.20).

**Статус реализации:** Python (`requirements.txt`, PyPI) — Sprint 25;
Node (`package.json`, npm) — Sprint 26; C#/.NET (`*.csproj`,
`Directory.Packages.props`, `packages.config`, NuGet) — **реализовано в
Sprint 57** (контракт — §3.15.1). `ecosystem=all` (или отсутствие параметра)
возвращает объединённый отчёт по всем найденным экосистемам.

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/repositories/{id}/dependencies` | `refresh?: bool`, `ecosystem?: python\|node\|dotnet\|all` | `DependencyReport` |

`DependencyReport`:

```json
{
  "repository_id": 1,
  "checked_at": "2026-11-06T10:00:00Z",
  "summary": {
    "total": 18,
    "outdated": 4,
    "up_to_date": 12,
    "unknown": 1,
    "ignored": 1
  },
  "ecosystems": [
    {
      "ecosystem": "python",
      "manifest": "backend/requirements.txt",
      "manifests": ["backend/requirements.txt"],
      "status": "ok",
      "source": "mixed",
      "total": 14,
      "outdated": 3,
      "up_to_date": 10,
      "unknown": 1,
      "ignored": 0,
      "packages": [
        {
          "name": "fastapi",
          "declared": "fastapi>=0.110,<1.0",
          "current": "0.110.0",
          "latest": "0.115.6",
          "status": "outdated",
          "kind": "range",
          "severity": "minor",
          "manifest_line": 3,
          "manifest_section": null,
          "manifest_path": "backend/requirements.txt"
        }
      ],
      "error": null
    }
  ]
}
```

**Статусы:**

- `ecosystem.status ∈ {ok, no_manifest, parse_error, unavailable}`.
- `ecosystem.source ∈ {registry, cache, mixed, stale_cache, none}`.
- `package.status ∈ {outdated, current, unknown, ignored}`.
- `package.kind ∈ {exact, range, vcs, path, workspace}`.
- `package.severity ∈ {major, minor, patch}` — только для `outdated`; для
  диапазона считается от нижней границы.

**Инварианты отчёта:**

- `ecosystems` содержит запрошенные ecosystem (по умолчанию все три);
  отсутствующий манифест — запись `status=no_manifest`, а не 404/500.
- Манифесты ищутся до `DEPENDENCY_MANIFEST_MAX_DEPTH` (default 3) ниже корня;
  `node_modules`, `.venv`, `venv`, `dist`, `build`, `target`, `vendor`, `.git`,
  `bin`, `obj`, `.vs`, `packages` (legacy NuGet restore) и кэши игнорируются.
  `manifests` — относительные POSIX-пути; `manifest` — первый путь для
  обратной совместимости.
- Пакеты из нескольких манифестов дедуплицируются по имени: `exact` важнее
  диапазона, диапазон с версией — важнее диапазона без версии. Провенанс
  сохраняется в `manifest_path`.
- `summary` — сумма счётчиков по всем запрошенным ecosystem; для одного
  ecosystem совпадает с его счётчиками.
- `total = outdated + up_to_date + unknown + ignored` для каждого ecosystem.
- `checked_at` верхнего уровня — момент формирования отчёта; `checked_at`
  отдельного пакета не отдаётся, но stale-состояние видно через `source`.

**Правила сравнения (v0.5.0):**

- Python: `==` → `exact`; `~=`, `>=`, `>`, `<=`, `<` → `range`. `current` —
  точная версия для `exact` или нижняя граница диапазона; если граница не
  извлекается — `current=null`, `status=unknown`.
- Python: `-e`, VCS, local path и URL → `ignored`; `-r` include читается
  относительно манифеста, только внутри корня репозитория, глубина ≤ 3;
  `-c`/constraints не раскрываются.
- Node: `1.2.3` → `exact`; `^`, `~`, `>=`, `*`, `latest` →
  `range`/`unknown`. `workspace:`, `file:`, `link:`, `portal:`, `git+`,
  `github:`, `http(s):`, `npm:` → `ignored`.
- .NET: `1.2.3` и `[1.2.3]` → `exact`; `[1.0,2.0)`, `1.*`, `1.2.*`,
  `*` → `range`; `ProjectReference`, `Reference` и локальные пути →
  `ignored`; `PackageReference` без `Version` при отсутствии CPM,
  `Version="$(Property)"` и `Condition` → `unknown` (причина в §3.15.1).
- `declared` сохраняет исходное объявление; extras, environment markers и hashes
  не участвуют в сравнении.
- `manifest_line` — 1-based строка для `requirements.txt` и XML-элемента
  `.csproj`/`Directory.Packages.props`; для `package.json` — `null`.
  `manifest_section` — `dependencies`/`devDependencies` для Node,
  `PackageReference`/`PackageVersion`/`packages.config` для .NET, иначе `null`.
- `severity` считается по первой различающейся части версии (major/minor/patch)
  от `current` к `latest`.
- Транзитивные зависимости и lock-файлы **не** анализируются.

**Кэш:** `DEPENDENCY_CACHE_TTL_SECONDS` (default 86400 = 24 ч), ключ
`<registry>:<normalized-name>` (`pypi:`, `npm:`, `nuget:`), таблица
`dependency_cache` (переживает перезапуск). `refresh=true` обходит TTL для
запрошенного репозитория и обновляет кэш. При ошибке реестра отдаётся
stale-кэш с `source=stale_cache`, если он есть.

**Rate limits и ошибки:** concurrency ≤ `DEPENDENCY_CHECK_CONCURRENCY` (default 4),
timeout `DEPENDENCY_HTTP_TIMEOUT` (default 5 с), backoff на 429/5xx (0.5/1/2 с).
Ошибка одного пакета не скрывает остальные. `error` — строка: для registry-ошибок
используются коды `rate_limited`, `registry_unavailable`, `timeout`; для
`parse_error` — сообщение. Пакет, отсутствующий в реестре (404), получает
`latest=null`, `status=unknown`. При недоступном реестре и отсутствии кэша —
`ecosystem.status=unavailable`, HTTP 200 (частичный отчёт).

#### 3.15.1. .NET / NuGet (v1.3.0, Sprint 57 — реализовано)

> **Статус:** реализовано в Sprint 57 (`dotnet_parser.py`,
> `nuget_client.py`), см. [`TODO_V1.3.0.md`](../TODO_V1.3.0.md). Ограничения
> парсинга — KI-025, решение — ADR-0018.

**Манифесты:**

| Файл | Что читаем | Приоритет версии |
|------|------------|------------------|
| `*.csproj`, `*.fsproj`, `*.vbproj` | `PackageReference Include="..." Version="..."` / `VersionOverride="..."` | 1 |
| `Directory.Packages.props` | `PackageVersion Include="..." Version="..."` (Central Package Management) | 2 |
| `packages.config` | `<package id="..." version="..." />` (legacy, best effort) | 3 |

- `PackageReference` без `Version` разрешается через ближайший
  `Directory.Packages.props` (поиск вверх до корня репозитория); если CPM нет —
  `status=unknown`, `kind=range`.
- `VersionOverride` важнее `Version` и центральной версии
  (`CentralPackageVersionOverrideEnabled`).
- `PrivateAssets="all"` и `developmentDependency="true"` помечают пакет как
  dev (`is_dev=true`); это не влияет на сравнение версий/CVE, но показывается
  в UI.
- XML-парсинг — `xml.etree.ElementTree` с запретом DTD/внешних сущностей;
  namespace MSBuild снимается. Лимиты: файл ≤ 256 KiB, глубина ≤ 64,
  элементов `PackageReference`/`PackageVersion` ≤ 2000 на файл. Битый XML или
  превышение лимита → ошибка в `ecosystem.error`; если не удалось прочитать
  ни одного пакета — `status=parse_error`.
- MSBuild-выражения (`$(...)`), `Condition`, `Import`, `Choose/When` **не
  вычисляются**: пакет получает `status=unknown`, `current=null`; схема
  пакета не расширяется. Это осознанный отказ от «угадывания» (KI-025).
- Несколько `TargetFrameworks` не дублируют пакеты; дедупликация по имени,
  `exact` важнее `range`. Провенанс — `manifest_path`.
- `bin/`, `obj/`, `.vs/`, `packages/` и `.git` при discovery игнорируются.

**NuGet-клиент:**

- `GET https://api.nuget.org/v3-flatcontainer/{id-lower}/index.json`
  (`id` — нижний регистр, URL-encode) → список версий.
- `latest` — максимальная stable-версия по SemVer 2.0.0; prerelease
  игнорируются. Если stable-версий нет — `latest=null`, `status=unknown`.
- 404 → `latest=null`, `status=unknown` (не ошибка экосистемы); 429/5xx —
  backoff 0.5/1/2 с (max 3 попытки), затем `registry_unavailable`.
- Timeout `DEPENDENCY_HTTP_TIMEOUT` (5 с), concurrency
  `DEPENDENCY_CHECK_CONCURRENCY` (4), User-Agent `IIRuchating/1.3`.
- Кэш `dependency_cache`, ключ `nuget:<lower-id>`, TTL 24 ч; stale-while-
  revalidate и single-flight — как для PyPI/npm.
- Приватные фиды, `NuGet.config` credentials и аутентификация — вне scope
  v1.3.0.

**Пример записи ecosystem:**

```json
{
  "ecosystem": "dotnet",
  "manifest": "src/Demo.Api/Demo.Api.csproj",
  "manifests": ["src/Demo.Api/Demo.Api.csproj", "Directory.Packages.props"],
  "status": "ok",
  "source": "registry",
  "total": 3,
  "outdated": 1,
  "up_to_date": 2,
  "unknown": 0,
  "ignored": 0,
  "packages": [
    {
      "name": "Newtonsoft.Json",
      "declared": "13.0.3",
      "current": "13.0.3",
      "latest": "13.0.4",
      "status": "outdated",
      "kind": "exact",
      "severity": "patch",
      "manifest_line": 18,
      "manifest_section": "PackageReference",
      "manifest_path": "src/Demo.Api/Demo.Api.csproj",
      "is_dev": false
    }
  ],
  "error": null
}
```

**CVE (§3.16):** для .NET в OSV передаётся `ecosystem="NuGet"`; имена пакетов
case-insensitive; `version_source=exact` для литерала/`[x.y.z]`,
`lower_bound` — для диапазона. Неразрешимые версии попадают в
`unknown_packages` с причиной `unresolved_version` и не считаются
проверенными.

**Read-only:** `dotnet restore/build/publish/list` в рамках аудита не
запускаются; MSBuild не вычисляется. `dotnet list`/`dotnet add` допускаются
только в §3.20 по явному подтверждению.

---

### 3.16. Security — CVE и Secret Scanning (v0.6.0, Sprint 28)

Проверка **объявленных** зависимостей на известные уязвимости через OSV.dev и
базовый поиск секретов в рабочей директории. Репозиторий только читается:
пакеты не устанавливаются/не обновляются, секреты не редактируются.

**Статус реализации:** Sprint 28 — реализовано (`SecurityService`,
`OsvClient`, `SecretScanner`). С v0.8.0 CVE-сканер использует общий
`ManifestDiscovery` и проверяет вложенные `requirements.txt`/`package.json`;
`manifests[]` перечисляет источники. С v1.3.0 (Sprint 57) проверяется и
экосистема .NET: `ecosystem="dotnet"`, в OSV — `NuGet` (§3.15.1).

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/repositories/{id}/security` | `refresh?: bool`, `include_secrets?: bool (default true)`, `min_severity?: critical\|high\|medium\|low\|all (default high)` | `SecurityReport` |

`SecurityReport`:

```json
{
  "repository_id": 1,
  "checked_at": "2026-11-06T10:00:00Z",
  "status": "ok",
  "summary": {
    "total_packages": 18,
    "packages_checked": 15,
    "vulnerable": 2,
    "critical": 0,
    "high": 2,
    "medium": 0,
    "low": 0,
    "unknown": 3,
    "secrets_found": 1
  },
  "ecosystems": [
    {
      "ecosystem": "python",
      "manifest": "backend/requirements.txt",
      "manifests": ["backend/requirements.txt"],
      "status": "ok",
      "total_packages": 14,
      "packages_checked": 14,
      "vulnerabilities": [
        {
          "package": "requests",
          "version": "2.19.0",
          "version_source": "exact",
          "osv_id": "GHSA-9wx4-h78v-vm56",
          "cve_ids": ["CVE-2018-18074"],
          "severity": "high",
          "cvss_score": 7.5,
          "summary": "Credentials could be sent to a different host",
          "fixed_version": "2.20.0",
          "references": ["https://github.com/advisories/GHSA-9wx4-h78v-vm56"]
        }
      ],
      "unknown_packages": [
        {"name": "some-lib", "reason": "unresolved_range"}
      ],
      "error": null
    },
    {
      "ecosystem": "node",
      "manifest": "package.json",
      "status": "no_manifest",
      "total_packages": 0,
      "packages_checked": 0,
      "vulnerabilities": [],
      "unknown_packages": [],
      "error": null
    }
  ],
  "secrets": {
    "status": "ok",
    "files_scanned": 812,
    "truncated": false,
    "findings": [
      {
        "file": "backend/.env.example",
        "line": 12,
        "type": "github_token",
        "severity": "high",
        "confidence": "high",
        "preview": "ghp_****1234"
      }
    ],
    "error": null
  },
  "error": null
}
```

#### 3.16.1. CVE: статусы и версии

- `ecosystem.status ∈ {ok, no_manifest, parse_error, unavailable}` — те же
  значения, что в §3.15; частичный отчёт всегда HTTP 200.
- `status` верхнего уровня — `unavailable`, только если **все** ecosystem с
  манифестом недоступны; иначе `ok` (включая `no_manifest` и частичные ошибки).
- `total_packages` — объявленные пакеты с разрешимой или неразрешимой версией
  (`ignored`-пакеты не входят); `packages_checked + unknown ≤ total`, разница —
  пакеты, которые не удалось проверить (OSV недоступен и кэша нет).
- `version_source ∈ {exact, lower_bound}`:
  - `exact` — версия из `==` / точного `package.json` / литерала `1.2.3` или
    `[1.2.3]` в .NET;
  - `lower_bound` — нижняя граница диапазона (`>=`, `^`, `~`, `[1.0,2.0)` и
    т.п.); результат считается приблизительным и помечается в UI.
- Пакеты, для которых версию извлечь нельзя, попадают в `unknown_packages`
  (`reason ∈ {unresolved_range, unresolved_version, unsupported_kind,
  registry_missing, osv_unavailable}`) и **не** считаются проверенными.
  `summary.unknown` — их количество.
- `severity ∈ {critical, high, medium, low, unknown}`:
  CVSS v3 ≥ 9.0 → `critical`, 7.0–8.9 → `high`, 4.0–6.9 → `medium`,
  < 4.0 → `low`; при отсутствии CVSS используется severity из OSV, иначе
  `unknown`.
- `min_severity` фильтрует `vulnerabilities[]`, но **не** меняет `summary`
  (счётчики всегда по полному набору) — чтобы фильтр не скрывал общую картину.
- `summary.vulnerable` — число уникальных уязвимых пакетов; `critical/high/…` —
  число уязвимостей соответствующей severity (одна уязвимость может содержать
  несколько CVE).
- Дедупликация по `osv_id`; `cve_ids` — алиасы вида `CVE-*`;
  `fixed_version` — минимальная исправленная версия из `affected`.
- Ошибка OSV по одному ecosystem не скрывает второй и не обнуляет `secrets`.
  При недоступном OSV и отсутствии кэша — `status=unavailable`, HTTP 200.

#### 3.16.2. Кэш и лимиты

- `security_cache`: ключ `osv:<ecosystem>:<package>:<version>`
  (`osv:pypi:`, `osv:npm:`, `osv:nuget:`), TTL
  `SECURITY_CACHE_TTL_SECONDS` (default **21600** = 6 ч), переживает перезапуск.
- `refresh=true` обходит TTL для запрошенного репозитория и обновляет кэш.
- Concurrency ≤ `SECURITY_CHECK_CONCURRENCY` (default 4), timeout
  `SECURITY_HTTP_TIMEOUT` (default 10 с), backoff на 429/5xx (0.5/1/2 с).
- При ошибке OSV и наличии stale-записи отдаётся кэш; `error` содержит причину
  (`rate_limited`, `timeout`, `osv_unavailable`), `checked_at` показывает момент
  формирования отчёта.

#### 3.16.3. Secret Scanning (базовый)

- Сканируется **рабочая директория**, не история Git.
- Источник файлов: `git ls-files -z -co --exclude-standard` — tracked-файлы и
  untracked-файлы, не покрытые `.gitignore`. Вне Git-репозитория (или при ошибке
  `git`) используется рекурсивный обход с теми же исключениями.
- Пропускаются: бинарные файлы, файлы больше `SECRET_SCAN_MAX_FILE_BYTES`
  (default **1048576** = 1 MiB), каталоги `.git`, `node_modules`, `.venv`,
  `vendor`, `dist`, `build`, `target`. Лимит `SECRET_SCAN_MAX_FILES`
  (default **5000**); при превышении `secrets.truncated=true` и
  `secrets.status=partial`.
- Правила (`type`): `aws_access_key`, `aws_secret_key`, `github_token`, `jwt`,
  `private_key`. Regex-набор фиксирован в ARCHITECTURE §12.6; произвольные
  пользовательские правила в v0.6.0 не поддерживаются.
- `preview` — **маскированный** фрагмент (`ghp_****1234`, `eyJ****`); полное
  значение не возвращается и не логируется.
- `severity ∈ {high, medium}` и `confidence ∈ {high, medium}` — по типу правила.
- Ложные срабатывания: строка с маркером `# iiruchating:ignore-secret`
  исключается; `include_secrets=false` пропускает сканирование целиком
  (`secrets.status=skipped`). Ограничения — KI-012.
- `secrets.status ∈ {ok, skipped, partial, unavailable}`; `partial` — часть
  файлов не прочитана (права/размер/лимит).
- Кэш сканирования — in-memory, `SECRET_SCAN_TTL_SECONDS` (default **300**);
  `refresh=true` обходит кэш. В БД результаты секретов не сохраняются.

---

### 3.17. Insights — Hotspots и DORA-lite (v0.6.0, Sprint 29)

Анализ Git-истории репозитория: файлы с высоким churn и частота коммитов в
ветке. Только чтение (`git log`, `git rev-parse`); `fetch` не выполняется.

**Статус реализации:** Sprint 29 — реализовано (`InsightsService`).

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/repositories/{id}/insights` | `days?: int (default 30, 1..365)`, `refresh?: bool` | `InsightsReport` |

`InsightsReport`:

```json
{
  "repository_id": 1,
  "checked_at": "2026-11-06T10:00:00Z",
  "status": "ok",
  "window": {
    "days": 30,
    "since": "2026-10-08",
    "until": "2026-11-06",
    "branch": "main",
    "hotspots_days": 90
  },
  "hotspots": [
    {"file": "backend/app/services/status_service.py", "count": 17}
  ],
  "commit_frequency": [
    {"date": "2026-10-08", "count": 3},
    {"date": "2026-10-09", "count": 0}
  ],
  "summary": {
    "commits": 42,
    "per_day": 1.4,
    "per_week": 9.8
  },
  "error": null
}
```

#### 3.17.1. Hotspots

- Окно фиксировано: `INSIGHTS_HOTSPOTS_DAYS` (default **90** ≈ 3 месяца),
  команда `git log --no-merges --name-only --since="3 months ago" --format=`.
- `count` — число коммитов, затронувших файл (не строки diff); merge-коммиты
  исключены, один коммит считается один раз на файл.
- Возвращается **топ-5** (`INSIGHTS_HOTSPOTS_LIMIT`), сортировка `count` desc,
  при равенстве — `file` asc (детерминизм).
- Фильтруются:
  - удалённые/отсутствующие в рабочей директории файлы;
  - документация `*.md`;
  - lock-файлы (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`,
    `poetry.lock`, `uv.lock`, `Cargo.lock`, `go.sum`, `packages.lock.json`,
    `project.assets.json`, `*-lock.json`, `*.lock`);
  - generated/minified (`*.min.js`, `*.min.css`, `*.map`, `*.snap`);
  - каталоги `node_modules`, `.venv`, `venv`, `vendor`, `dist`, `build`,
    `target`, `bin`, `obj`, `.vs`, `__pycache__`, `.git`.
- Переименования не отслеживаются (без rename detection): churn до переезда
  остаётся на старом пути.
- Нет коммитов в окне или всё отфильтровано → `hotspots=[]`, `status=ok`.

#### 3.17.2. DORA-lite (Commit Frequency)

- Это **прокси** частоты поставки по коммитам в ветке, а не учёт реальных
  деплоев; UI подписывает блок как «commit frequency».
- `branch` определяется по порядку: `main` → `master` → текущая ветка HEAD.
  Если ни одна не найдена — `status=no_branch`, `branch=null`.
- Команда `git log <branch> --since="<days> days ago" --format=%ad --date=short`;
  merge-коммиты включены (каждый push в ветку — потенциальный деплой).
- `commit_frequency` содержит **все дни окна** (`days` точек, заканчивая
  сегодняшним), пропуски заполняются `count=0`.
- `summary.commits = Σ count`; `per_day = commits / days`,
  `per_week = per_day * 7`, округление до 2 знаков.
- Shallow clone (`.git/shallow`) даёт `status=shallow_clone`: числа могут быть
  занижены, вместо тихой неверной картины.

#### 3.17.3. Статусы, кэш и производительность

- `status ∈ {ok, partial, no_branch, shallow_clone, timeout, unavailable}`.
  Приоритет: `timeout` → `unavailable` (обе команды не удались) →
  `no_branch` → `shallow_clone` → `partial` (одна из команд) → `ok`.
- `error` — код причины: `timeout`, `git_unavailable`, `branch_not_found`,
  `partial`, `output_too_large`; для `ok`/`shallow_clone` — `null`.
- In-memory кэш `INSIGHTS_CACHE_TTL_SECONDS` (default **300**), ключ
  `repo_path + days`; `refresh=true` обходит кэш.
- Git-вызовы асинхронные (`asyncio.create_subprocess_exec`), таймаут
  `INSIGHTS_GIT_TIMEOUT_SECONDS` (default **10**); при timeout процесс
  убивается, ответ — `status=timeout`, HTTP 200.
- Размер stdout ограничен **8 MiB**; превышение → `status=partial`,
  `error=output_too_large`, а не 500.
- `GIT_OPTIONAL_LOCKS=0`; рабочая директория и индекс не изменяются.

---

### 3.18. AI assistant (v0.7.0, Sprints 32–33)

Локальный LLM (Ollama / LM Studio) через OpenAI-совместимый API. Эндпоинты
**только читают** репозиторий и ничего не коммитят; результат — черновик,
который пользователь подтверждает вручную.

#### 3.18.1. Генерация commit message

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/repositories/{id}/ai/commit-message` | — | `CommitMessageSuggestion` |

`CommitMessageSuggestion`:

```json
{
  "repository_id": 1,
  "message": "feat(api): add repository security endpoint",
  "source": "llm",
  "provider": "lmstudio",
  "model": "qwen2.5-coder-7b-instruct",
  "truncated": false,
  "diff_chars": 4200,
  "files_changed": 3,
  "warnings": [],
  "generated_at": "2026-11-06T10:00:00Z"
}
```

**Правила:**

- Требуется хотя бы один tracked-изменённый файл
  (`dirty.modified + dirty.staged > 0`); иначе `400` с
  `detail="Нет изменений для коммита"`. Пустой `git diff HEAD` — тот же ответ.
- Источник diff: `git diff HEAD --no-color --no-ext-diff --unified=3`
  (staged + unstaged); бинарные файлы не дают текстового diff.
- Лимит `LLM_MAX_DIFF_CHARS` (default **10000** символов). При обрезке
  добавляется строка `[diff truncated]`, `truncated=true`,
  `warnings=["diff_truncated"]`.
- `llm_enabled=false` → `409 llm_disabled`; не-loopback endpoint без
  `llm_allow_remote=true` → `409 llm_remote_not_allowed`.
- Промпт: «Ты — senior разработчик. Напиши commit message в формате
  Conventional Commits (feat/fix/docs/refactor). Опиши изменения кратко и по
  делу. Ответь только текстом коммита, без кавычек.» Diff передаётся как
  данные, не как инструкции.
- `LLM` timeout `LLM_TIMEOUT_SECONDS` (default **30**). При недоступности,
  таймауте, 5xx или невалидном ответе — `503` с
  `detail="LLM недоступна. Проверьте настройки."`; fallback-сообщение не
  генерируется.
- Markdown-обёртки и окружающие кавычки снимаются; пустой ответ считается
  ошибкой LLM.
- Diff, промпт и ответ LLM **не** сохраняются в БД и не логируются (только
  метаданные: модель, символы diff, source, длительность).
- `source` пока всегда `llm`;
  `provider ∈ {ollama, lmstudio, openai_compatible}`.

#### 3.18.2. Объяснение CVE (Sprint 33)

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/repositories/{id}/ai/cve-explain` | `{cve_id, summary}` | `CveExplanation` |

`CveExplanation`:

```json
{
  "explanation": "Уязвимость позволяет отправить учётные данные на чужой хост. Обновите пакет до 2.20.0.",
  "cached": false,
  "model": "qwen2.5-coder-7b-instruct",
  "generated_at": "2026-11-06T10:00:00Z"
}
```

**Правила:**

- `cve_id` (1..128) и `summary` (1..4000) обязательны; `summary` — описание
  уязвимости, которое передаёт UI из `SecurityReport`.
- Промпт: «Ты — эксперт по безопасности. Объясни разработчику простым языком,
  в чем опасность уязвимости {cve_id} (описание: {summary}). Как её исправить?
  Ответь кратко, 2-3 предложения.»
- Кэш `ai_cache` (см. §4): ключ `cve-explain:<cve_id>:<model>`, TTL
  `AI_CACHE_TTL_SECONDS` (default **604800** = 7 дней); при попадании
  `cached=true` и LLM не вызывается.
- `llm_enabled=false` → `409 llm_disabled`; не-loopback endpoint без
  `llm_allow_remote=true` → `409 llm_remote_not_allowed`.
- LLM timeout/недоступна → `503` с
  `detail="LLM недоступна. Проверьте настройки."`; fallback-текст не
  подставляется.
- `repository_id` проверяется на существование (`404`); сам репозиторий не
  читается и не меняется.
- Объяснение не влияет на `SecurityReport`; в `ai_cache` хранится только текст
  объяснения и модель.

---

### 3.19. Global dependencies (v0.7.0, Sprint 33)

Сводка объявленных версий популярных пакетов по всем `tracked=true`
репозиториям. Только чтение; пакеты не обновляются.

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/dashboard/global-dependencies` | `refresh?: bool (default false)` | `GlobalDependencyReport` |

`GlobalDependencyReport`:

```json
{
  "checked_at": "2026-11-06T10:00:00Z",
  "ecosystems": {
    "python": [
      {
        "name": "fastapi",
        "latest_version": "0.116.0",
        "distribution": [
          {"version": "0.110.0", "projects": ["alpha"]},
          {"version": "0.115.0", "projects": ["beta"]}
        ],
        "versions_count": 2,
        "projects_count": 2,
        "unification_needed": true
      }
    ],
    "node": [
      {
        "name": "react",
        "latest_version": "19.2.0",
        "distribution": [
          {"version": "18.0.0", "projects": ["alpha"]},
          {"version": "19.0.0", "projects": ["beta"]}
        ],
        "versions_count": 2,
        "projects_count": 2,
        "unification_needed": true
      }
    ]
  },
  "summary": {
    "repositories": 34,
    "packages": 120,
    "unification_candidates": 8
  },
  "error": null
}
```

**Правила:**

- Агрегация — `DependencyService.get_report(..., ecosystem="all")` для каждого
  tracked-репозитория (парсеры §3.15 + registry latest / `dependency_cache`).
  `providers` не вызываются повторно при попадании в кэш.
- Версия проекта — `package.current` (`exact` или нижняя граница диапазона);
  пакеты `ignored`/без версии не входят. Один проект учитывается один раз на
  версию.
- `distribution` — версия → список проектов (alias или basename пути),
  сортировка по возрастанию версии.
- `latest_version` — максимальная известная latest из отчётов
  `DependencyService`; `null`, если реестр не ответил и кэша нет.
- `unification_needed = versions_count > 1`; `projects_count` — уникальные
  проекты, использующие пакет.
- Пакеты сортируются по `projects_count` desc, `name` asc; возвращается не более
  `GLOBAL_ANALYTICS_LIMIT` (default **50**). `summary.packages` считает все
  пакеты до ограничения.
- `summary.repositories` — число tracked-репозиториев;
  `unification_candidates` — пакеты с `unification_needed=true`.
- In-memory кэш ответа `GLOBAL_ANALYTICS_CACHE_TTL_SECONDS` (default **3600** =
  1 час); `refresh=true` обходит кэш и передаёт `refresh` в `DependencyService`.
- Ошибка отдельного репозитория не скрывает остальные: `error="partial_errors"`,
  HTTP 200.

---

### 3.20. Automated dependency updates (v0.7.0, Sprint 34; .NET — v1.3.0, Sprint 57 — реализовано)

Явная мутация: обновление пакетов выбранного репозитория. Только при
`confirm=true`, на чистом worktree и с аудитом. Вне этого действия система
остаётся read-only.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/repositories/{id}/actions/update-dependencies` | `{confirm:true, ecosystem: python\|node\|dotnet}` | `ActionLog` |
| POST | `/repositories/actions/update_dependencies_all` | `{confirm:true, ecosystem: python\|node\|dotnet, repo_ids?: int[]}` | `202 {status:"accepted"}` |

**.NET (v1.3.0 — реализовано):**

- Read-only проверка: `dotnet list <project> package --outdated --no-restore`
  запускается при наличии `dotnet` в PATH. Без CLI — `409 dotnet_unavailable`.
- Мутация: для каждого найденного outdated-пакета выполняется
  `dotnet add <project> package <id> --no-restore` (без `--version` — ставится
  последняя stable-версия). Обход проектов ограничен 20 файлами.
- Нет проекта → `409 no_manifest`. `restore`/`build`/`publish`, `--force` и
  удаление `packages.lock.json` запрещены.
- `dotnet add` не коммитит изменения; пользователь проверяет diff сам.

**Preflight:**

- `confirm != true` → `400 confirmation_required`.
- Чистота worktree проверяется через `git status --porcelain`; любой вывод →
  `409` с `detail="Worktree must be clean"`. Действие не выполняется, попытка
  пишется в `action_log` (`status=error`, `error=dirty_worktree`).
- Ошибка `git status` → `409 git_unavailable`, тоже с записью в `action_log`.
- Менеджер: Python — `requirements.txt` → `pip`; Node — `pnpm-lock.yaml` →
  `pnpm`, иначе `package.json` → `npm`; .NET — `*.csproj`/`*.sln` → `dotnet`.
  Нет манифеста → `409 no_manifest` (попытка логируется).

**Команды:**

- Python: `pip install -r requirements.txt --upgrade`
  (запускается как `python -m pip install ...`).
- Node: `pnpm update` или `npm update`.
- .NET: `dotnet list <project> package --outdated --no-restore`, затем
  `dotnet add <project> package <id> --no-restore` (реализовано v1.3.0);
  `dotnet restore/build/publish` не запускаются.
- Выборочное обновление пакетов и флаги `--force`/`--legacy-peer-deps` не
  поддерживаются; `git`-мутации и удаление lock-файлов запрещены.

**Ограничения и аудит:**

- Timeout `DEPENDENCY_UPDATE_TIMEOUT_SECONDS` (default **180**); по таймауту
  процесс убивается, `ActionLog.status=error`, `error=timeout`.
- Вывод ограничен `DEPENDENCY_UPDATE_MAX_OUTPUT_CHARS` (default **10000**
  символов); credentials в URL редактируются (`https://****@host/...`).
- Ошибка команды (`pip`/`pnpm`/`npm`) не даёт 500: `ActionLog.status=error`,
  HTTP `409`, `detail=error`.
- `ActionLog`: `action="update-dependencies"`, `command`, `status`,
  `exit_code`, `output`, `error`, `duration_ms`, `actor=local|bulk`.
- Bulk: concurrency 2, `actor=bulk`; один упавший репозиторий не отменяет
  остальные.
- Обновление может изменить `package.json`/lockfile и окружение backend;
  UI предупреждает пользователя (KI-014). Автоматического коммита нет.
- ADR-0011 фиксирует preflight-политику и границы доверия.

---

### 3.21. README и документы репозитория (v0.8.0, Sprint 35)

Read-only просмотр README и связанных Markdown-документов прямо из карточки
проекта. Raw HTML не исполняется; backend отдаёт исходный Markdown, frontend
рендерит его безопасным встроенным парсером.

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/repositories/{id}/readme` | — | `ReadmeResponse` |
| GET | `/repositories/{id}/docs` | `path` (relative, 1…2048) | `RepositoryDocResponse` |

`ReadmeResponse`:

```json
{
  "repository_id": 20,
  "path": "README.md",
  "name": "IIRuchating — мониторинг и анализ локальных проектов",
  "version": "v0.7.0",
  "content": "# IIRuchating ..."
}
```

`RepositoryDocResponse`: `{repository_id, path, content}`.

**Метаданные README:**

- `name` — первый H1 (`# ...`) без Markdown-разметки; fallback — имя каталога.
- `version` — первое совпадение `Версия/Version: vX.Y.Z` или badge-версии в
  первых 80 строках; иначе `null`.

**Безопасность и лимиты:**

- Читаются только `.md`, `.markdown`, `.txt`; размер ≤ **512 KiB** (413 при
  превышении).
- Путь обязан оставаться внутри корня репозитория; `..`, абсолютные пути,
  `~` и `.git/**` отклоняются (400).
- Отсутствующий README/документ — 404; неверный путь — 400; слишком большой
  файл — 413.
- Backend не выполняет HTML и не ходит по внешним ссылкам; frontend открывает
  внешние ссылки в новой вкладке, внутренние `.md`-ссылки — через `/docs`.

---

### 3.22. Remote duplicates (v0.8.0, Sprint 37)

Поиск локальных клонов, указывающих на один и тот же remote URL. Read-only:
Git-конфигурация только читается, репозитории не изменяются.

| Метод | Путь | Ответ |
|-------|------|-------|
| GET | `/dashboard/duplicates` | `DuplicatesResponse` |

```json
{
  "checked": 25,
  "groups": [
    {
      "remote_url": "github.com/acme/project",
      "repositories": [
        {"id": 1, "path": "K:/Projects/AI/project", "name": "project"},
        {"id": 2, "path": "K:/Projects/GitFlic/project", "name": "project"}
      ]
    }
  ]
}
```

**Правила:**

- URL берётся из `remote.origin.url`; fallback — `github_full_name` /
  `gitflic_full_name`.
- Нормализация: `https://`, `ssh://`, `git@host:owner/repo`, trailing `.git`,
  регистр host/path; локальные пути и URLs без host игнорируются.
- В `groups` попадают только URL с ≥ 2 репозиториями; `checked` — число
  проверенных Repository.
- Ошибка чтения одного remote не даёт 500 — репозиторий пропускается.

---

### 3.23. AI unification advice (v0.8.0, Sprint 37)

Совет локального LLM, на какую версию пакета унифицироваться, если в проектах
объявлены разные версии.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/dashboard/global-dependencies/ai-advice` | `{ecosystem, package}` | `UnificationAdvice` |

`UnificationAdvice`: `{ecosystem, package, advice, cached, model, generated_at}`.

**Правила:**

- Совет доступен только при `unification_needed=true`; иначе `400`.
- Пакет ищется в актуальном глобальном отчёте; отсутствие — `404`.
- LLM выключена, remote endpoint без opt-in или LLM не ответила — `503`.
- Промпт содержит только имя пакета и распределение версий/проектов; код,
  diff и секреты не отправляются.
- Кэш `ai_cache`, ключ
  `unification-advice:<ecosystem>:<package>:<model>`, TTL
  `AI_CACHE_TTL_SECONDS` (default 7 дней); при попадании `cached=true`.
- Ответ LLM ограничен `MAX_EXPLANATION_CHARS` (2000).

---

### 3.24. AI recommendations, agent tasks & LLM test (v0.8.0, Sprint 38)

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/ai/dashboard-advice` | `{language?: ru\|en}` | `DashboardAdvice` |
| POST | `/repositories/{id}/ai/agent-task` | `{language?: ru\|en}` | `AgentTask` |
| POST | `/settings/llm/test` | — | `LLMTestResponse` |

`DashboardAdvice`: `{advice, cached, model, generated_at, stats}`.
`stats` содержит `repositories`, `current`, `dirty`, `diverged`, `behind`,
`ahead`, `no_upstream`, `outdated_packages`, `high_critical_cves`.

**Dashboard advice:**

- Агрегаты собираются из tracked-репозиториев: статусы из БД, outdated — через
  `DependencyService`, high/critical CVE — через `SecurityService`.
- LLM получает только числа; промпт просит 2–3 приоритетные рекомендации.
- Ответ кэшируется в `ai_cache` на **1 час**, ключ
  `dashboard-advice:<language>:<model>`; `cached=true` при попадании.
- LLM disabled/remote → `409`; LLM недоступна → `503`.

**Agent task:**

- `AgentTask`: `{task, model, generated_at}`; `task` — Markdown.
- Контекст: `state`, dirty-счётчики, branch/upstream, ahead/behind, конфликтные
  файлы, темы последних 8 коммитов. Код и diff не отправляются.
- LLM disabled/remote → `409`; LLM недоступна → `503`.
- Задача не выполняется автоматически и не пишется в репозиторий.

**LLM test:**

- Два коротких `ping`: `/v1/chat/completions` для `model_name` (чат) и
  `/v1/embeddings` для `embedding_model` (RAG). HTTP 200 в обоих случаях,
  даже если одна из моделей недоступна.
- `{chat: {status, latency_ms, error}, embedding: {status, latency_ms, error},
  status, latency_ms, error}`; верхнеуровневые поля сохранены для старых
  клиентов, `status="ok"` только если обе модели ответили.
- Коды ошибок чата: `llm_disabled`, `llm_remote_not_allowed`, `timeout`,
  `connection_error`, `http_<code>`, `invalid_json`, `invalid_response`.
- Коды ошибок эмбеддингов: `embedding_model_not_configured`,
  `embedding_remote_not_allowed`, `timeout`, `connection_error`,
  `http_<code>`, `invalid_json`, `invalid_response`.

---

### 3.25. AI provider profiles (v0.8.0, Sprint 39)

OpenAI-совместимые профили провайдеров. Активный профиль имеет приоритет над
`LLM_*` из `config.py`; при отсутствии активного профиля используется fallback
конфигурации (обратная совместимость).

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/settings/ai-providers` | список профилей (ключи замаскированы) |
| POST | `/settings/ai-providers` | создать профиль |
| PATCH | `/settings/ai-providers/{id}` | обновить профиль |
| DELETE | `/settings/ai-providers/{id}` | удалить профиль |
| POST | `/settings/ai-providers/{id}/activate` | сделать профиль активным |
| POST | `/settings/ai-providers/gigachat/auth` | OAuth-авторизация GigaChat (§3.27) |
| POST | `/settings/ai-providers/{id}/gigachat/refresh` | обновить токен GigaChat |

`AIProviderRead`: `{id, name, base_url, api_key, model_name, embedding_model,
is_active, created_at, provider_type, auth_type, client_id, has_client_secret,
oauth_scope, oauth_expires_at}`.
`api_key` всегда маскируется (`sk-a****1234`); `client_secret` и
`access_token` **никогда** не возвращаются; пустой ключ не отдаётся.
`model_name` — модель чата; `embedding_model` — отдельная модель для
`/v1/embeddings` (RAG), может быть `null`.

**Инварианты:**

- `name` уникально; конфликт — `409`.
- Первый созданный профиль автоматически становится активным.
- `activate` сбрасывает `is_active` у остальных; активным может быть только
  один профиль.
- `PATCH` с пустым/отсутствующим `api_key` сохраняет текущий ключ.
- `PATCH` с пустой строкой `embedding_model` очищает поле (`null`).
- Чат-методы (`generate_commit_message`, `review_code`, `chat` и др.)
  используют `model_name`; `embed()`/`/v1/embeddings` — только
  `embedding_model` активного профиля. Если поле пустое, RAG возвращает
  `503 embedding_model_not_configured` и не подставляет чат-модель.
- Миграция `016` добавляет nullable-колонку `embedding_model` и заполняет её
  `text-embedding-nomic-embed-text-v1.5` для существующих
  OpenAI-совместимых профилей; GigaChat-профили остаются пустыми.
- `LLMService` перечитывает активный профиль из БД при каждом вызове
  (изменения применяются без перезапуска).
- Если активного профиля нет — fallback на `LLM_ENABLED`, `LLM_BASE_URL`,
  `LLM_MODEL`, `LLM_API_KEY`.
- Remote endpoint по-прежнему требует `LLM_ALLOW_REMOTE=true` (для GigaChat
  OAuth проверка remote не применяется — это штатный облачный провайдер).
- Удаление профиля не удаляет историю `ai_cache`; активный профиль может
  отсутствовать.
- **v0.9.0 (реализовано, S43):** добавлены `provider_type`
  (`openai_compatible` | `gigachat`) и `auth_type` (`api_key` | `oauth`); для
  GigaChat — поля OAuth (§3.27). Существующие профили считаются
  `openai_compatible`/`api_key`.

---

### 3.26. Code search / RAG (v0.9.0, Sprint 44 — реализовано)

> **Статус:** реализовано. PostgreSQL использует `pgvector`, desktop/SQLite —
> расширение `sqlite-vec` (`vec0`) с Python-fallback; при отсутствии обоих
> бэкендов эндпоинты отвечают `503 rag_unavailable`.

Семантический поиск по README, `docs/` и исходному коду tracked-репозиториев.
Индексация **read-only**: файлы читаются, рабочая директория, индекс Git и
`.git` не изменяются.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/api/v1/search/code` | `CodeSearchRequest` | `CodeSearchResponse` |
| POST | `/api/v1/search/code/index` | `{repository_ids?: int[], force?: bool}` | `202 CodeIndexJob` |
| GET | `/api/v1/search/code/status` | — | `CodeIndexStatus` |

**`CodeSearchRequest`:**

```json
{
  "query": "где у меня настроен Redis?",
  "repository_ids": [1, 2],
  "limit": 10,
  "min_score": 0.2,
  "language": "python"
}
```

- `query` — 3–500 символов, обязателен;
- `repository_ids` — опционально, только tracked-репозитории;
- `limit` — 1–50 (default 5);
- `min_score` — 0–1 (default 0.2), порог косинусной близости;
- `language` — опционально (`python`, `typescript`, `csharp`, `xml`,
  `markdown`, …).

**`CodeSearchResponse`:**

```json
{
  "query": "где у меня настроен Redis?",
  "model": "text-embedding-3-small",
  "took_ms": 42,
  "indexed_repositories": 34,
  "stale": false,
  "results": [
    {
      "repository_id": 1,
      "repository_name": "ai-teacher_python",
      "path": "backend/app/core/redis.py",
      "start_line": 10,
      "end_line": 42,
      "language": "python",
      "snippet": "REDIS_URL = ...",
      "score": 0.83,
      "url": "https://github.com/owner/repo/blob/HEAD/backend/app/core/redis.py#L10"
    }
  ]
}
```

**Инварианты:**

- Векторное хранилище — PostgreSQL + `pgvector` (сервер) или SQLite +
  `sqlite-vec` (`vec_chunks`, cosine KNN) в desktop; если C-расширение не
  загрузилось, поиск считает косинус в Python по JSON-эмбеддингам
  (`sqlite_vec_unavailable_fallback_to_python`).
- Эмбеддинги — OpenAI-compatible `/v1/embeddings`. Модель берётся из
  `embedding_model` активного профиля (§3.25), а при его отсутствии — из
  `EMBEDDING_MODEL` (default `text-embedding-3-small`, 1536 измерений);
  локальная модель настраивается через профиль и `EMBEDDING_DIMENSIONS`
  (например, `nomic-embed-text` → 768). `embedding_base_url`/`embedding_api_key`
  остаются настройками RAG; remote embeddings — только
  `EMBEDDING_ALLOW_REMOTE=true`.
- Если у активного профиля `embedding_model` не задан, поиск/индексация
  возвращают `503 embedding_model_not_configured` с указанием открыть
  «Настройки → AI Провайдеры». HTTP/сетевые ошибки эмбеддингов —
  `503 embedding_model_unavailable: проверьте настройки AI-провайдера`.
  Чат-модель `model_name` для эмбеддингов **не** используется.
- Индекс инкрементальный: hash файла/чанка; неизменённые чанки не
  переэмбеддируются.
- `stale=true`, если индекс старше последнего сканирования/HEAD; автоматическая
  переиндексация не запускается.
- Сниппет ≤ 400 символов; запросы, фрагменты и эмбеддинги не логируются;
  секреты в сниппете маскируются.
- Ошибки: `400` — валидация; `503 rag_unavailable` — нет pgvector/LM Studio;
  `504 embedding_timeout`; `429` — при включённом локальном rate-limit.

**`CodeIndexJob`:** `{status: "started"|"running"|"completed"|"failed",
message, started_at}`.
**`CodeIndexStatus`:** `{indexed_repositories, indexed_chunks, last_indexed_at,
running, errors[]}`.

---

### 3.27. GigaChat OAuth (v0.9.0, Sprint 43 — реализовано)

> **Статус:** реализовано. Профиль `provider_type="gigachat"` использует
> OAuth 2.0; OpenAI-совместимые профили работают без изменений.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/api/v1/settings/ai-providers/gigachat/auth` | `GigaChatAuthRequest` | `GigaChatAuthResponse` |

**`GigaChatAuthRequest`:**

```json
{
  "profile_name": "GigaChat",
  "client_id": "00000000-0000-0000-0000-000000000000",
  "client_secret": "secret",
  "scope": "GIGACHAT_API_PERS",
  "model_name": "GigaChat",
  "base_url": "https://gigachat.devices.sberbank.ru/api/v1",
  "activate": false
}
```

- `scope`: `GIGACHAT_API_PERS` (default) | `GIGACHAT_API_B2B` |
  `GIGACHAT_API_CORP`;
- `profile_name` уникально; при совпадении профиль обновляется, а не дублируется;
- `client_secret` обязателен для `gigachat/auth`; повторное обновление без
  секрета — через `POST /settings/ai-providers/{id}/gigachat/refresh`;
- `activate=true` делает профиль активным (сбрасывает `is_active` у остальных).

**`GigaChatAuthResponse`:**

```json
{
  "profile_id": 7,
  "status": "ok",
  "expires_at": "2026-11-08T12:30:00Z",
  "model_name": "GigaChat"
}
```

**Инварианты:**

- OAuth 2.0: `POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth`,
  `Content-Type: application/x-www-form-urlencoded`, `RqUID: <uuid4>`,
  `Authorization: Basic base64(client_id:client_secret)`,
  body `scope=<scope>`; ответ `{access_token, expires_at}` (`expires_at` — ms
  epoch).
- `access_token` и `client_secret` **никогда** не возвращаются в API, не
  попадают в логи, `action_log` и `ai_cache`. В БД хранятся server-only;
  в ответах — только маска.
- Токен кэшируется в памяти по `profile_id` и обновляется за
  `GIGACHAT_TOKEN_REFRESH_MARGIN_SECONDS` (default 60) до истечения; refresh —
  single-flight (mutex).
- При `401` — один принудительный refresh и повтор; повторный `401` →
  `provider_unauthorized`. Ошибки: `invalid_client`, `unsupported_scope`,
  `provider_unavailable`, `timeout`, `http_<code>`.
- TLS-сертификат НУЦ Минцифры — через `GIGACHAT_CA_BUNDLE`; отключение
  проверки сертификата запрещено.
- `LLMService.resolve()` выбирает `GigaChatProvider` по
  `provider_type="gigachat"`; OpenAI-совместимые профили работают без изменений.
- Токен живёт ~30 минут (KI-018); UI показывает `expires_at` и предлагает
  повторную авторизацию, не спамя запросами.

---

### 3.28. Single-user authentication (v1.0.0, Sprint 47 — реализовано)

> **Статус:** реализовано. При `AUTH_ENABLED=true` API защищён JWT; при
> `false` остаётся локальный режим без входа. См. [`TODO_V1.0.md`](../TODO_V1.0.md)
> и ADR-0016. С v1.3.0 (Sprint 58) добавлены роли `Admin`/`Auditor`
> и audit log — §3.31.

Один пользователь без регистрации, ролей и мультитенантности. Auth включается
флагом `AUTH_ENABLED`; при `true` все роуты, кроме перечисленных ниже, требуют
валидный JWT.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/api/v1/auth/login` | `{username, password}` | `LoginResponse` + `Set-Cookie` |
| GET | `/api/v1/auth/me` | — | `{id, username}` |
| POST | `/api/v1/auth/logout` | — | `204`, cookie очищена |
| PATCH | `/api/v1/users/me/password` | `{old_password, new_password}` | `{status: "ok"}` |
| POST | `/api/v1/users/{id}/reset-password` | `{new_password}` | `{status: "ok"}`, только admin |

- Смена своего пароля (S61-004): `old_password` проверяется через bcrypt; при
  ошибке — `400 invalid_old_password`; `new_password` — 8–1024 символа; пишется
  аудит `password_changed` (без пароля/hash).
- Сброс пароля администратором: `403 insufficient_role` для аудитора,
  `404 user_not_found` для неизвестного id, аудит `user_password_reset`.

**`LoginResponse`:**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_at": "2026-11-09T08:00:00Z",
  "user": {"id": 1, "username": "owner"}
}
```

- JWT: HS256, claims `sub` (user id), `iat`, `exp`, `jti`; секрет
  `AUTH_JWT_SECRET` (≥32 байта), TTL `AUTH_TOKEN_TTL_SECONDS` (default 604800 —
  7 дней).
- Cookie: `iiruchating_session=<jwt>; HttpOnly; SameSite=Lax; Path=/;
  Max-Age=<ttl>`; `Secure` — если запрос пришёл по HTTPS.
- Middleware принимает cookie **или** `Authorization: Bearer <jwt>`.
- Без токена: `/api/v1/health`, `/api/v1/metrics`, `/api/v1/auth/login`
  доступны; остальные — `401`.
- Ошибки: `401 invalid_credentials`, `401 token_expired`,
  `403 user_disabled`, `429 too_many_attempts`.
- Rate-limit логина: 5 попыток / 60 с на IP+username; пароль и JWT не логируются.
- Пароль хранится только как bcrypt-hash (cost ≥ 12); в ответах и логах hash
  отсутствует.
- Bootstrap: при пустой `users` пользователь создаётся из
  `ADMIN_USERNAME` (default `admin`) + `ADMIN_PASSWORD` (default `admin`);
  пароль сразу хэшируется bcrypt. При `AUTH_ENABLED=true` и ошибке bootstrap
  приложение не стартует.
- `AUTH_ENABLED` default `true`; для локального `127.0.0.1` можно выключить
  (`false`), для Docker/LAN рекомендуется `true` (см. `.env.example`).
- Frontend: `/login`, `AuthProvider`, protected routes, редирект на `/login`
  при `401`, logout; в desktop-сборке — Bearer fallback (KI-020).
- Read-only политика не меняется: auth только закрывает доступ, но не даёт
  права на мутации без существующих подтверждений.

**Схема `users`:**

```
users(
  id, username* UNIQUE, hashed_password, is_active BOOLEAN,
  created_at, last_login_at NULL
)
```

**Переменные окружения:** `AUTH_ENABLED`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`,
`AUTH_JWT_SECRET`, `AUTH_TOKEN_TTL_SECONDS`, `AUTH_LOGIN_RATE_LIMIT`,
`AUTH_LOGIN_RATE_WINDOW_SECONDS`.

---

### 3.29. AI code review, conflict resolver & release notes (v1.2.0)

> **Статус:** AI Code Review реализован в Sprint 53; conflict resolver и
> release notes — реализованы в Sprint 54. Контракты ниже — обязательные для
> реализации; см. [`TODO_V1.2.0.md`](../TODO_V1.2.0.md).
> Все эндпоинты **read-only**: читают diff/файлы/историю и возвращают текст, но
> не пишут файлы, не меняют индекс и `.git`.
>
> Для выбора тегов в UI: `GET /api/v1/repositories/{id}/tags` →
> `{repository_id, tags: string[]}` (только чтение).

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/api/v1/repositories/{id}/ai/code-review` | `CodeReviewRequest` | `CodeReviewResponse` |
| POST | `/api/v1/repositories/{id}/ai/resolve-conflict` | `ConflictResolveRequest` | `ConflictResolveResponse` |
| POST | `/api/v1/repositories/{id}/ai/release-notes` | `ReleaseNotesRequest` | `ReleaseNotesResponse` |

**`CodeReviewRequest`:**

```json
{
  "language": "ru",
  "refresh": false
}
```

- `language` — `ru` | `en` (default `ru`);
- `refresh` — обойти `ai_cache` (default `false`).

**`CodeReviewResponse`:**

```json
{
  "repository_id": 1,
  "review": "## Потенциальные баги\n- ...",
  "source": "llm",
  "provider": "lmstudio",
  "model": "qwen2.5-coder-7b-instruct",
  "cached": false,
  "generated_at": "2026-11-09T12:00:00Z",
  "files_reviewed": 4,
  "diff_chars": 1234,
  "truncated": false,
  "warnings": []
}
```

**Code review — правила:**

- Diff: `git diff HEAD --no-color --no-ext-diff --unified=3` (staged +
  unstaged); если HEAD недоступен/пуст — fallback `git diff --cached`;
  бинарные файлы пропускаются. Если оба пусты — `400` («Нет изменений»).
- Чанкинг: diff режется по файлам/ханкам на части ≤
  `AI_CODE_REVIEW_CHUNK_CHARS` (default 5000), максимум
  `AI_CODE_REVIEW_MAX_CHUNKS` (default 8). Общий лимит
  `AI_CODE_REVIEW_MAX_CHARS` (default 40000); при превышении —
  `truncated=true`, `warnings=["diff_truncated"]`.
- Промпт: Senior Code Reviewer; найти баги, проблемы безопасности, предложить
  улучшения; ответ — Markdown со ссылками на файлы/строки.
- Ответ ограничен 8000 символов (константа `MAX_CODE_REVIEW_CHARS`).
- Кэш `ai_cache` с TTL `AI_CACHE_TTL_SECONDS` (default 604800):
  `code-review:<repo_id>:<state_hash>:<model>:<prompt_version>`;
  `state_hash` включает diff и язык; `refresh=true` обходит кэш.
- В LLM не отправляются файлы вне diff, `.env`, ключи; секреты в diff
  маскируются.

**`ConflictResolveRequest`:**

```json
{
  "file_path": "src/app.ts",
  "language": "ru",
  "refresh": false
}
```

**`ConflictResolveResponse`:**

```json
{
  "repository_id": 1,
  "file_path": "src/app.ts",
  "resolved": "// merged full file...",
  "blocks": 1,
  "provider": "lmstudio",
  "model": "qwen2.5-coder-7b-instruct",
  "cached": false,
  "generated_at": "2026-11-09T12:00:00Z",
  "truncated": false,
  "warnings": ["verify_before_apply"]
}
```

**Conflict resolver — правила:**

- `file_path` — относительный путь внутри репозитория; traversal/symlink за
  пределы репозитория → `403 path_outside_repository`; бинарный файл →
  `400 binary_file`; отсутствует → `404 file_not_found`; файл больше
  `AI_CONFLICT_MAX_FILE_BYTES` (default 1048576) → `400 file_too_large`.
- Ищутся маркеры `<<<<<<<`, `=======`, `>>>>>>>`; если их нет →
  `400` («Конфликтов не найдено»).
- Каждый блок ≤ `AI_CONFLICT_MAX_CHARS` (default 20000), не более
  `AI_CONFLICT_MAX_BLOCKS` (default 10); при превышении — `truncated=true`,
  необработанные блоки остаются с маркерами.
- Промпт: объединить обе стороны, сохранить поведение/стиль; вернуть только код
  без маркеров и пояснений.
- `resolved` — **полный файл** с заменёнными блоками; UI показывает его и
  копирует, но **не пишет файл** (read-only).
- Ответ всегда содержит `warnings=["verify_before_apply"]` (KI-023);
  при частичной обработке добавляется `conflict_truncated`.
- Кэш `ai_cache` с TTL `AI_CACHE_TTL_SECONDS`:
  `resolve-conflict:<repo_id>:<file_path>:<hash>:<model>:<prompt_version>`;
  кэшируются только объединённые блоки, файл пересобирается из актуального
  содержимого.

**`ReleaseNotesRequest`:**

```json
{
  "from_tag": "v1.0.0",
  "to_tag": "v1.1.0",
  "language": "ru",
  "refresh": false
}
```

**`ReleaseNotesResponse`:**

```json
{
  "repository_id": 1,
  "from_tag": "v1.0.0",
  "to_tag": "v1.1.0",
  "changelog": "## [1.1.0] - 2026-11-09\n### Added\n- ...",
  "commits": 42,
  "provider": "lmstudio",
  "model": "qwen2.5-coder-7b-instruct",
  "cached": false,
  "generated_at": "2026-11-09T12:00:00Z",
  "truncated": false,
  "warnings": []
}
```

**Release notes — правила:**

- `from_tag` обязателен; `to_tag` опционален (default `HEAD`); теги
  проверяются read-only через `git rev-parse --verify`.
- История: `git log from..to --oneline --no-decorate`; лимит
  `AI_RELEASE_NOTES_MAX_COMMITS` (default 500), общий лимит
  `AI_RELEASE_NOTES_MAX_CHARS` (default 20000); при превышении —
  `truncated=true`, `warnings=["commits_truncated"]`.
- Промпт: сгруппировать по Keep a Changelog (`Added`, `Changed`, `Fixed`),
  не выдумывать изменения.
- Ответ — Markdown; ограничен 12000 символов (`MAX_RELEASE_NOTES_CHARS`).
- В LLM отправляются только oneline-коммиты; diff и код не отправляются.
- Кэш `ai_cache` с TTL `AI_CACHE_TTL_SECONDS`:
  `release-notes:<repo_id>:<from>:<to>:<hash>:<model>:<prompt_version>`.

**Общие ошибки AI-эндпоинтов §3.29:**

- `404 repository_not_found` — репозиторий не tracked;
- `409 llm_disabled` / `409 llm_remote_not_allowed` — LLM выключена или remote
  без opt-in;
- `503 llm_unavailable` — LLM недоступна/ошибка;
- `504 llm_timeout` — превышен `LLM_TIMEOUT_SECONDS`;
- `400` — невалидные параметры/пустой diff/нет конфликтов/неверный диапазон
  тегов.

---

### 3.30. Conversational RAG (v1.2.0 — реализовано)

> **Статус:** реализовано в Sprint 55. Требуется PostgreSQL + `pgvector`;
> на SQLite — `503 rag_unavailable`.

Чат с базой знаний: вопрос → embedding → top-k чанков из `code_chunks` →
LLM-ответ с цитатами на источники. Использует ту же индексацию, что §3.26.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/api/v1/search/chat` | `ChatRequest` | `ChatResponse` |

**`ChatRequest`:**

```json
{
  "query": "В каких проектах я использую Redis?",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "repository_ids": [1, 2],
  "limit": 5,
  "min_score": 0.2
}
```

- `query` — 3–2000 символов, обязателен;
- `history` — ≤ `AI_CHAT_MAX_HISTORY` (default 10) сообщений, только
  `user`/`assistant`;
- `repository_ids` — опционально, только tracked-репозитории;
- `limit` — 1–20 (default 5, top-k чанков);
- `min_score` — 0–1 (default 0.2).

**`ChatResponse`:**

```json
{
  "answer": "Redis используется в проектах ... [1][2]",
  "sources": ["demo/src/redis.py:10-20"],
  "citations": [
    {
      "repository_id": 1,
      "repository_name": "demo",
      "path": "src/redis.py",
      "start_line": 10,
      "end_line": 20,
      "language": "python",
      "snippet": "REDIS_URL = ...",
      "score": 0.83,
      "url": "https://github.com/owner/repo/blob/HEAD/src/redis.py#L10"
    }
  ],
  "model": "qwen2.5-coder-7b-instruct",
  "embedding_model": "nomic-embed-text",
  "took_ms": 120
}
```

**Правила:**

- PostgreSQL + `pgvector` или SQLite + `sqlite-vec` (v1.4.0); при недоступном
  хранилище — `503 rag_unavailable`, остальное приложение работает (KI-022).
  Эмбеддинги — только `embedding_model` активного профиля (§3.25).
- Embedding запроса → top-k чанков (`limit`, `min_score`) → контекст с
  `repository/path/start_line/end_line`.
- Промпт: отвечать только по переданным чанкам; если данных нет — явно сказать
  об этом; чанки — **данные**, не инструкции (защита от prompt injection).
- Ответ ≤ `AI_CHAT_MAX_OUTPUT_CHARS` (default 4000); ссылки `[n]`
  соответствуют `sources[n-1]`, `citations` содержат метаданные для ссылок.
- История и сообщения не логируются; секреты в чанках маскируются.
- Кэш в v1.2.0 не используется: чат интерактивный, история влияет на ответ.
- Ошибки: `400` — валидация; `503 rag_unavailable` / `llm_unavailable`;
  `504 embedding_timeout` / `llm_timeout`; `429` — локальный rate-limit.

---

### 3.31. Team edition — роли и Audit Log (v1.3.0, Sprint 58 — реализовано)

> **Статус:** реализовано в Sprint 58. Расширяет single-user auth §3.28;
> контракты ниже актуальны для текущей реализации.

Две роли: `admin` (полный доступ) и `auditor` (только чтение). Роль хранится в
БД и проверяется на каждом запросе; claim JWT `role` носит информационный
характер и не является источником прав. При `AUTH_ENABLED=false` действует
неявный локальный `admin`.

**`GET /api/v1/auth/me`:** `{id, username, role, is_active, created_at,
last_login_at}`.

**Матрица прав:**

| Возможность | `admin` | `auditor` |
|-------------|---------|-----------|
| Чтение дашборда, репозиториев, зависимостей, CVE, insights, AI | ✅ | ✅ |
| README/docs, экспорт workspace/Markdown | ✅ | ✅ |
| `fetch`/`pull`/`push`/`stash`/`commit`, track/untrack, refresh | ✅ | ❌ `403 insufficient_role` |
| `update-dependencies`, bulk-actions | ✅ | ❌ `403` |
| Изменение настроек, AI-профилей | ✅ | ❌ `403` |
| Пользователи и `audit` | ✅ | ❌ `403` |
| Запуск scan и переиндексация RAG | ✅ | ❌ `403` (просмотр готовых отчётов — да) |

**Пользователи (admin-only):**

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| GET | `/api/v1/users` | — | `User[]` |
| POST | `/api/v1/users` | `{username, role, password?}` | `201 UserInviteResponse` |
| PATCH | `/api/v1/users/{id}` | `{role?, is_active?, password?}` | `User` |

`User`: `{id, username, role, is_active, created_at, last_login_at}`; hash
пароля не отдаётся. `UserInviteResponse`: `{user, temporary_password}`;
если пароль не передан, генерируется временный (≥ 8 символов). Пароль —
bcrypt cost ≥ 12. Новые пользователи по умолчанию получают `auditor`,
bootstrap-пользователь — `admin`. Нельзя понизить/отключить себя
(`409 cannot_demote_self`) или последнего активного admin (`409 last_admin`).
Ошибки: `400 validation_error`, `403 insufficient_role`,
`404 user_not_found`, `409 username_exists`.

**Audit Log API (admin-only):**

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

- `action` — стабильный код: `scan_started`, `repo_push`,
  `repo_<action>` (fetch/pull/stash/commit), `dep_update`,
  `settings_updated`, `user_created`, `user_updated`, `role_changed`.
- `entity_type`/`entity_id` — объект действия (`repository`, `scan`, `user`,
  `settings`, `ai_provider`); у `settings` `entity_id=null`.
- `details` — только метаданные (экосистема, статус, имена ключей настроек,
  роль до/после). Токены, пароли, секреты, содержимое файлов и diff не
  пишутся; полезная нагрузка ограничена 4000 символами.
- Append-only: нет API изменения/удаления; retention-политика пока не
  реализована.
- Сортировка `created_at` desc, `id` desc; `limit` 1..200, `offset` ≥ 0.
- UI: страница `/admin/audit` только для admin (ленивая), таблица
  дата/пользователь/действие/объект/детали, пагинация, `aria`; для auditor
  пункт меню скрыт. `action_log` остаётся отдельным журналом вывода команд.

---

### 3.32. SAST — статический анализ кода (v1.3.0, Sprint 59 — реализовано)

> **Статус:** реализовано в Sprint 59 (`app/services/sast_service.py`).
> Инструменты опциональны; их отсутствие не даёт 500.

Поиск небезопасного кода (`eval`, `exec`, SQL-конкатенация, небезопасный
`subprocess`) в рабочей директории. Только чтение; код проекта не исполняется.

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/api/v1/repositories/{id}/sast` | `tools?: all\|bandit\|semgrep\|eslint (default all)`, `min_severity?: critical\|high\|medium\|low\|all (default all)`, `refresh?: bool` | `SastReport` |

**`SastReport`:**

```json
{
  "repository_id": 1,
  "checked_at": "2026-11-11T10:00:00Z",
  "status": "partial",
  "tools": [
    {"name": "bandit", "status": "ok", "version": null, "duration_ms": 820, "error": null},
    {"name": "semgrep", "status": "unavailable", "version": null, "duration_ms": 0, "error": "not_installed"}
  ],
  "summary": {"total": 4, "critical": 0, "high": 2, "medium": 2, "low": 0, "unknown": 0},
  "findings": [
    {
      "tool": "bandit",
      "rule_id": "B602",
      "severity": "high",
      "confidence": "high",
      "category": "security",
      "cwe": "CWE-78",
      "file": "app/utils.py",
      "line": 42,
      "column": null,
      "message": "subprocess call with shell=True",
      "snippet": "subprocess.run(cmd, shell=True)",
      "fingerprint": "sha256:..."
    }
  ],
  "truncated": false,
  "error": null,
  "cached": false
}
```

**Правила:**

- `bandit` (Python) — внешний бинарник или `python -m bandit`; ищется при
  старте запроса. `semgrep` — внешний бинарник, запускается только с локальным
  набором правил (`SAST_SEMGREP_CONFIG` или bundled
  `app/sast_rules/default.yml`), `--metrics=off`, `--disable-version-check`;
  сеть и `--config auto` запрещены. Если semgrep недоступен, используется
  локальный `node_modules/.bin/eslint` (fallback).
- Отсутствие инструмента → `tool.status=unavailable`, остальные инструменты
  продолжают работу; HTTP 200.
- `status ∈ {ok, partial, unavailable}`: `partial` — часть инструментов
  недоступна/ошибка или превышен лимит; `unavailable` — ни один не отработал.
- `severity ∈ {critical, high, medium, low, unknown}`; маппинг: bandit
  HIGH→high, MEDIUM→medium, LOW→low; semgrep ERROR→high, WARNING→medium,
  INFO→low; eslint error→high, warning→medium. `min_severity` фильтрует
  `findings[]`, но **не** меняет `summary`.
- Дедупликация по `fingerprint` (file+line+rule+message); один паттерн от
  двух инструментов — одна запись с объединённым `tool`.
- Лимиты: timeout `SAST_TIMEOUT_SECONDS` (120), вывод ≤ 8 MiB, findings ≤
  `SAST_MAX_FINDINGS` (500); превышение → `truncated=true` и
  `status=partial`.
- `snippet` ≤ 300 символов, секреты маскируются; полные файлы и совпадения не
  логируются. Кэш `sast_cache` (TTL `SAST_CACHE_TTL_SECONDS`, default
  **86400** = 24 ч) по `repo_id + head_sha + dirty_hash + tools`;
  `refresh=true` обходит TTL. Недоступный результат не кэшируется.
- Ошибки: `404 repository_not_found`; `422` — неверный `tools`/`min_severity`.
  Недоступность инструментов и таймауты отражаются в отчёте, а не HTTP 500.
- Read-only: `git status --porcelain` после скана не меняется; `bin/`,
  `obj/`, `node_modules/`, `.venv/`, `vendor/` исключаются.
- UI: отдельный блок «Безопасность кода (SAST)» рядом с CVE; список
  `file:line`, severity, правило, сниппет и кнопка «Исправить с AI»
  (`POST /repositories/{id}/ai/sast-explain`, `ai_cache`).

---

### 3.33. Автоматические PR — генерация конфигураций (v1.3.0, Sprint 59 — реализовано)

> **Статус:** реализовано в Sprint 59. Приложение **не** делает commit/push и
> не создаёт PR: оно генерирует текст конфигурации, который пользователь
> копирует сам.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/api/v1/repositories/{id}/automation/generate` | `{tool: "dependabot" \| "renovate"}` | `AutomationConfigResponse` |

**`AutomationConfigResponse`:**

```json
{
  "tool": "dependabot",
  "path": ".github/dependabot.yml",
  "content": "version: 2\nupdates:\n  - package-ecosystem: pip\n...",
  "content_hash": "...",
  "ecosystems": ["dotnet", "node", "python"],
  "warnings": []
}
```

- `tool ∈ {dependabot, renovate}`; экосистемы определяются автоматически по
  найденным манифестам (`ManifestDiscovery`): Python, Node, .NET.
- Dependabot: `version: 2`, `updates[]` c `package-ecosystem`
  (`pip`/`npm`/`nuget`), `directory`, `schedule.interval=weekly`,
  `open-pull-requests-limit=5`, `groups` для minor/patch.
- Renovate: `$schema`, `extends: ["config:recommended"]`, `schedule`,
  `packageRules` для группировки minor/patch, `enabledManagers` по найденным
  экосистемам.
- `content_hash = sha256(content)`; `path` — только
  `.github/dependabot.yml` или `renovate.json`.
- Если манифестов нет — `warnings=["no_manifests"]`, конфигурация всё равно
  возвращается.
- Эндпоинт ничего не пишет в репозиторий, не делает commit/push и не требует
  `confirm`. Ошибки: `404 repository_not_found`, `422` — неверный `tool`.
- UI: модалка «Автоматизация» (lazy) с кнопками «Сгенерировать Dependabot»,
  «Сгенерировать Renovate», предпросмотром YAML/JSON и кнопкой
  «Скопировать»; предупреждение об отсутствии autopush.

---

### 3.34. Global Tech Debt Dashboard (v1.5.0, Sprint 63 — план)

> **Статус:** запланировано на v1.5.0 (Sprint 63). Контракт фиксируется до
> реализации; `GET /dashboard` и `GET /dashboard/global-dependencies` не
> меняются. Агрегация только читает существующие отчёты и кэши.

Сводная картина технического долга по всем `tracked=true` репозиториям:
outdated-пакеты, CVE, dirty-файлы, diverged-ветки и (с Sprint 64) IaC-проблемы.
Тяжёлые проверки не запускаются на каждый запрос: сервис использует
`repository_status`, `dependency_cache`, `security_cache` и in-memory кэш.

#### 3.34.1. `GET /api/v1/dashboard/global-stats`

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/api/v1/dashboard/global-stats` | `refresh?: bool (default false)` | `GlobalStatsReport` |

**`GlobalStatsReport`:**

```json
{
  "checked_at": "2026-11-11T12:00:00Z",
  "cached": false,
  "scope": {"repositories": 34, "tracked": 30, "scanned": 28, "skipped": 2},
  "summary": {
    "outdated_packages": 42,
    "unique_outdated_packages": 31,
    "vulnerabilities": {
      "critical": 1, "high": 5, "medium": 12, "low": 3, "unknown": 0,
      "total": 21, "unique_cves": 18
    },
    "dirty_files": 18,
    "diverged_branches": 4,
    "iac_issues": 0,
    "problem_types": [
      {"type": "outdated_packages", "count": 42, "severity": "medium"},
      {"type": "vulnerabilities", "count": 21, "severity": "high"},
      {"type": "dirty_files", "count": 18, "severity": "medium"},
      {"type": "diverged_branches", "count": 4, "severity": "high"},
      {"type": "iac_issues", "count": 0, "severity": "low"}
    ]
  },
  "repositories": [
    {
      "repository_id": 7,
      "name": "alpha",
      "path": "/projects/alpha",
      "status": "ok",
      "stale": false,
      "outdated_packages": 12,
      "vulnerabilities": {
        "critical": 1, "high": 2, "medium": 3, "low": 0, "unknown": 0, "total": 6
      },
      "dirty_files": 3,
      "diverged": true,
      "iac_issues": 0,
      "problem_score": 47,
      "error": null
    }
  ],
  "top_problematic": [
    {"repository_id": 7, "name": "alpha", "problem_score": 47}
  ],
  "errors": [],
  "error": null
}
```

**Правила:**

- `scope.repositories` — все репозитории, `scope.tracked` — `tracked=true`,
  `scope.scanned` — хотя бы один источник ответил, `scope.skipped` — tracked,
  но ни один источник не ответил (`status=error`).
- Агрегируются только `repositories.tracked=true`. Нет tracked-репозиториев →
  HTTP 200, `scope.tracked=0`, нулевые счётчики.
- `outdated_packages` — число экземпляров пакетов
  (`repository_id + ecosystem + name`) со `status="outdated"`;
  `unique_outdated_packages` — уникальные `ecosystem:name`.
- `vulnerabilities` — число advisory-записей по severity; `unique_cves` —
  уникальные `osv_id`/CVE. Один advisory в разных репозиториях считается
  экземпляром, но не уникальным CVE.
- `dirty_files` — сумма `modified + staged + untracked + conflicted` из
  `repository_status`; `diverged_branches` — число репозиториев в состоянии
  `diverged` (в текущей модели одна отслеживаемая ветка на репозиторий).
- `problem_score` = `outdated * 1 + critical * 10 + high * 5 + medium * 2 +
  low * 1 + unknown * 1 + dirty_files * 1 + diverged * 5 + iac_critical * 10 +
  iac_high * 5 + iac_medium * 2 + iac_low * 1`.
- `top_problematic` — до `GLOBAL_STATS_TOP_LIMIT` (default **5**) записей
  `{repository_id, name, problem_score}` по `problem_score` desc, затем
  `name` asc. Полный список — в `repositories[]`.
- `status ∈ {ok, partial, error}`: `partial` — хотя бы один источник
  недоступен/устарел; `error` — репозиторий не читается. `stale=true` —
  использован кэш с истёкшим TTL.
- Ошибка одного репозитория/источника не скрывает остальные: `errors[]`,
  HTTP 200. Ошибка всех источников → HTTP 200, нули,
  `error="all_sources_unavailable"` (не 500).
- In-memory кэш `GLOBAL_STATS_CACHE_TTL_SECONDS` (default **300** = 5 мин),
  single-flight; `refresh=true` обходит кэш и передаётся источникам.
  Concurrency ≤ `GLOBAL_STATS_CONCURRENCY` (default **4**). `dependency_cache`/
  `security_cache` обновляются только при истёкшем TTL, не на каждый запрос.
- `iac_issues` — additive-поле: до Sprint 64 всегда `0`; после — число
  IaC-findings severity `high|critical`. Контракт обратно совместим.
- Read-only: никаких `git fetch`, повторного сканирования диска, записи в
  репозитории и изменения `repository_status`.
- Ошибки: `422` — неверный `refresh`.
- UI: блок «Tech Debt Overview» на главном дашборде — карточки, Pie Chart по
  `problem_types`, Bar Chart по `top_problematic`; lazy charts, empty/partial/
  error, RU/EN, `aria`, клавиатурная навигация. Entry bundle < 90 kB gzip.

#### 3.34.2. `POST /api/v1/dashboard/global-stats/ai-advice`

| Метод | Путь | Тело | Параметры | Ответ |
|-------|------|------|-----------|-------|
| POST | `/api/v1/dashboard/global-stats/ai-advice` | `{language?: "ru" \| "en"}` | `refresh?: bool` | `GlobalStatsAdvice` |

**`GlobalStatsAdvice`:**

```json
{
  "generated_at": "2026-11-11T12:01:00Z",
  "summary": "Наибольший риск — 1 critical CVE и 4 diverged-репозитория…",
  "priorities": [
    {
      "title": "Закрыть critical CVE",
      "reason": "1 critical и 2 high advisory в двух репозиториях",
      "repository_id": 7,
      "action": "Обновить уязвимые пакеты и повторить CVE-скан"
    }
  ],
  "model": "qwen2.5-coder-7b-instruct",
  "cached": false
}
```

- В LLM отправляются только агрегаты `GlobalStatsReport`, имена/алиасы
  репозиториев и счётчики. Пути, код, diff, версии пакетов, описания CVE,
  токены и секреты **не** отправляются.
- `priorities[]` — до 5 записей `{title, reason, repository_id, action}`;
  `summary` ≤ 2000 символов; `action` — текстовая рекомендация, не команда.
- Ключ `ai_cache`: `global-stats-advice:<state_hash>:<model>:<prompt_version>:<language>`,
  TTL `AI_CACHE_TTL_SECONDS` (default 7 дней). `refresh=true` обходит кэш;
  `X-AI-Cache: hit|miss`; ошибки LLM не кэшируются.
- `LLM_ENABLED=false`, remote-guard или ошибка LLM → `503 ai_unavailable`.
  Тело необязательно; без тела — `language="ru"`. Доступ — `admin` и
  `auditor` (read-only AI).
- UI: панель «Что горит» с кнопкой генерации, индикатором кэша и
  503-сообщением; `aria-live` для результата, RU/EN.

---

### 3.35. Infrastructure as Code (IaC) Scanning (v1.5.0, Sprint 64 — план)

> **Статус:** запланировано на v1.5.0 (Sprint 64). Только локальный
> read-only анализ; Docker daemon, registry, сеть и сборка образов не
> используются.

#### 3.35.1. `GET /api/v1/repositories/{id}/iac`

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/api/v1/repositories/{id}/iac` | `refresh?: bool (default false)` | `IacReport` |

**Обнаружение файлов:** `Dockerfile`, `Dockerfile.*`, `*.Dockerfile`,
`docker-compose.yml|yaml`, `compose.yml|yaml` в рабочей директории; глубина
`IAC_MAX_DEPTH` (default **3**), исключения — `.git/`, `node_modules/`,
`.venv/`, `vendor/`, `dist/`, `build/`, `target/`. Symlink'и не
разыменовываются.

**`IacReport`:**

```json
{
  "repository_id": 1,
  "checked_at": "2026-11-11T12:00:00Z",
  "status": "ok",
  "files": [
    {"path": "Dockerfile", "kind": "dockerfile", "status": "ok", "error": null},
    {"path": "docker-compose.yml", "kind": "compose", "status": "ok", "error": null}
  ],
  "summary": {
    "total": 5, "critical": 1, "high": 2, "medium": 1, "low": 1,
    "unknown": 0, "files_scanned": 2
  },
  "findings": [
    {
      "rule_id": "IAC001",
      "severity": "high",
      "category": "dockerfile",
      "file": "Dockerfile",
      "line": 3,
      "message": "Container runs as root",
      "evidence": "USER root",
      "remediation": "Create an unprivileged user and switch with USER app",
      "fingerprint": "sha256:..."
    }
  ],
  "truncated": false,
  "error": null,
  "cached": false
}
```

**Правила и лимиты:**

| rule_id | severity | Файл | Условие |
|---------|----------|------|---------|
| `IAC001` | high | Dockerfile | финальный stage без `USER` или `USER root`/`USER 0` |
| `IAC002` | medium | Dockerfile | нет `HEALTHCHECK` или `HEALTHCHECK NONE` |
| `IAC003` | medium | Dockerfile | `FROM` без тега/digest или с `:latest` |
| `IAC004` | critical | compose | `privileged: true` |
| `IAC005` | high | compose | опубликованный порт слушает все интерфейсы (`0.0.0.0`/без `host_ip`); `127.0.0.1`/`::1` — безопасно |
| `IAC006` | high | compose | `network_mode: host` |
| `IAC007` | high | compose | bind-mount `/var/run/docker.sock` |
| `IAC008` | low | compose | `image` без тега или с `:latest` |

- `status ∈ {ok, partial, no_files, parse_error, unavailable}`: `no_files` —
  IaC-файлы не найдены (HTTP 200); `partial` — часть файлов не разобрана или
  превышен лимит; `parse_error` — все найденные файлы не разобраны;
  `unavailable` — репозиторий недоступен. При `IAC_ENABLED=false` — HTTP 200,
  `status="unavailable"`, `error="iac_disabled"`, `files=[]`.
- `files[]` — все найденные файлы, включая `parse_error`, сортировка по пути;
  `file.status ∈ {ok, parse_error}`, `error` — короткая причина без
  содержимого файла; `findings[]` — severity desc (`critical→unknown`), затем
  `file`, `line`.
- `severity ∈ {critical, high, medium, low, unknown}` — общая шкала CVE/SAST.
  `evidence` ≤ 300 символов, секреты маскируются; `fingerprint =
  sha256(rule_id + file + line + normalized_evidence)`; дубли схлопываются.
- Лимиты: `IAC_MAX_FILES` (default **100**) на репозиторий,
  `IAC_MAX_FILE_BYTES` (default **1048576** = 1 MiB),
  `IAC_MAX_FINDINGS` (default **200**), `IAC_TIMEOUT_SECONDS` (default **10**).
  Превышение → `truncated=true`, `status=partial`.
- Dockerfile: построчный state-machine (не один regex): BOM/CRLF, продолжения
  `\`, комментарии `#`, case-insensitive инструкции, multi-stage; оценивается
  финальный stage. `USER ${VAR}` не угадывается (правило не срабатывает);
  `FROM scratch` не требует `USER`. `HEALTHCHECK NONE` = отсутствие
  healthcheck. «Устаревший» `FROM` трактуется как unpinned/`:latest`;
  проверка новых версий через registry — вне scope (нет сети).
- compose: `yaml.safe_load` с лимитом размера, без custom constructors и
  выполнения кода; до 200 сервисов; поддержка short/long form `ports`.
  Ошибка YAML → `parse_error`.
- In-memory кэш `IAC_CACHE_TTL_SECONDS` (default **300**), ключ
  `repo_id + head_sha + dirty_hash + file_mtimes`; `refresh=true` обходит кэш.
  Недоступный/`parse_error` результат не кэшируется.
- Read-only и offline: `GIT_OPTIONAL_LOCKS=0`, `git status --porcelain` после
  запроса не меняется; `docker`/registry не вызываются. Ошибки:
  `404 repository_not_found`, `422` — неверный `refresh`; проблемы файлов
  отражаются в отчёте, а не HTTP 500.
- UI: блок «Инфраструктура» в деталях репозитория — severity, `file:line`,
  message, evidence, remediation; empty-state «IaC-файлы не найдены»,
  partial/error, `aria`, RU/EN, lazy-загрузка.

#### 3.35.2. `GET /api/v1/dashboard/global-iac`

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/api/v1/dashboard/global-iac` | `refresh?: bool (default false)` | `GlobalIacReport` |

**`GlobalIacReport`:**

```json
{
  "checked_at": "2026-11-11T12:00:00Z",
  "cached": false,
  "summary": {
    "repositories": 30, "files_scanned": 44,
    "total": 18, "critical": 1, "high": 6, "medium": 8, "low": 3, "unknown": 0
  },
  "repositories": [
    {
      "repository_id": 7, "name": "alpha", "path": "/projects/alpha",
      "files_scanned": 2, "total": 3, "critical": 1, "high": 1,
      "medium": 1, "low": 0, "unknown": 0, "status": "ok", "error": null
    }
  ],
  "top_findings": [
    {
      "repository_id": 7, "name": "alpha", "rule_id": "IAC004",
      "severity": "critical", "file": "docker-compose.yml", "line": 8,
      "message": "Service runs in privileged mode"
    }
  ],
  "errors": [],
  "error": null
}
```

- Агрегируются только `tracked=true`; `summary.repositories` — число
  опрошенных, `files_scanned` — сумма по отчётам.
- `top_findings` — до `IAC_GLOBAL_TOP_LIMIT` (default **10**) записей по
  severity desc, затем `repository_id`, `file`, `line`.
- Кэш `GLOBAL_IAC_CACHE_TTL_SECONDS` (default **300**), concurrency ≤
  `IAC_CONCURRENCY` (default **4**), single-flight; `refresh=true` обходит кэш.
- Ошибка одного репозитория → `status="partial"`/`error` в записи, HTTP 200;
  ошибка всех → HTTP 200, нули, `error="all_repositories_failed"`.
- На дашборде: компактная сводка «Инфраструктура» (critical/high/medium) и
  переход к топ-находкам/репозиторию; `summary.iac_issues` в §3.34 считается
  как число findings severity `high|critical`; RU/EN, `aria`.

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

users(                      -- v1.0.0 (Sprint 47); role v1.3.0 (Sprint 58)
  id, username* UNIQUE, hashed_password, is_active BOOLEAN,
  role TEXT NOT NULL DEFAULT 'admin',  -- admin | auditor
  created_at, last_login_at NULL
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

audit_log(                  -- v1.3.0 (Sprint 58)
  id, user_id→users NULL,
  action TEXT, entity_type TEXT NULL, entity_id TEXT NULL,
  details JSONB, created_at
)

app_settings(               -- S15-001
  key* TEXT PRIMARY KEY, value TEXT NULL, updated_at
)

dependency_cache(           -- v0.5.0
  key* TEXT PRIMARY KEY,    -- "pypi:fastapi" | "npm:react" | "nuget:newtonsoft.json"
  ecosystem TEXT,           -- pypi | npm | nuget
  package TEXT,             -- нормализованное имя
  latest_version TEXT NULL,
  etag TEXT NULL,
  payload JSONB,            -- последний ответ реестра (нормализованный)
  checked_at
)

security_cache(             -- v0.6.0 (Sprint 28)
  key* TEXT PRIMARY KEY,    -- "osv:pypi:requests:2.19.0" | "osv:nuget:newtonsoft.json:13.0.3"
  ecosystem TEXT,           -- pypi | npm | nuget
  package TEXT,
  version TEXT,             -- проверяемая версия (exact или lower_bound)
  payload JSONB,            -- нормализованный ответ OSV.dev
  checked_at
)

sast_cache(                 -- v1.3.0 (Sprint 59)
  key* TEXT PRIMARY KEY,    -- "<repo_id>:<head_sha>:<dirty_hash>:<tools>:<versions>:<rules_hash>"
  repository_id→repositories,
  payload JSONB,            -- нормализованный SastReport
  checked_at
)

ai_cache(                   -- v0.7.0 (Sprint 33), smart hash v0.9.0 (Sprint 43)
  key* TEXT PRIMARY KEY,    -- "<feature>:<scope>:<state_hash>:<model>:<prompt_version>"
  kind TEXT,                -- cve_explain | commit_message | dashboard_advice | ...
  model TEXT NULL,
  payload JSONB,            -- {explanation|advice|message, ...}
  checked_at
)

ai_provider_profiles(       -- v0.8.0 (Sprint 39), GigaChat v0.9.0 (Sprint 43)
  id, name* UNIQUE, base_url, api_key NULL, model_name,
  is_active BOOLEAN, created_at,
  -- v0.9.0 (реализовано, миграция 010):
  provider_type TEXT DEFAULT 'openai_compatible', -- openai_compatible | gigachat
  auth_type TEXT DEFAULT 'api_key',              -- api_key | oauth
  client_id TEXT NULL, client_secret TEXT NULL,
  oauth_scope TEXT NULL, oauth_expires_at, access_token TEXT NULL,
  -- v1.4.2 (миграция 016):
  embedding_model TEXT NULL  -- отдельная модель для /v1/embeddings; NULL = не настроена
)

code_chunks(                -- v0.9.0 (реализовано, Sprint 44; PostgreSQL + pgvector)
  id BIGSERIAL PRIMARY KEY,
  repository_id→repositories,
  path TEXT,
  chunk_index INT,
  start_line INT, end_line INT,
  language TEXT NULL,
  content TEXT,
  content_hash TEXT,        -- sha256 нормализованного чанка
  embedding vector(1536),   -- EMBEDDING_DIMENSIONS
  embedding_model TEXT,
  indexed_at,
  UNIQUE(repository_id, path, chunk_index, content_hash)
)
```

Индексы: `repositories(path)`, `repositories(tracked)`, `repositories(github_full_name)`, `repositories(gitflic_full_name)`, `repository_status(repository_id)`, `repository_mirror_status(repository_id)`, `scan_runs(started_at)`, `webhook_events(received_at)`, `webhook_events(provider, event_type)`, `dependency_cache(checked_at)`, `security_cache(checked_at)`, `ai_cache(checked_at)`, `ai_provider_profiles(is_active)`; **v0.9.0 (реализовано):** `code_chunks(repository_id)`, `code_chunks(content_hash)`, HNSW/IVFFlat по `code_chunks.embedding vector_cosine_ops`; **v1.3.0 (реализовано):** `audit_log(user_id)`, `audit_log(action)`, `audit_log(created_at)`, `sast_cache(checked_at)`.

**v1.5.0 (план):** новых таблиц и миграций нет. `GlobalStatsService` и
`IacService` (включая агрегатор `global-iac`) используют существующие
`repository_status`/`dependency_cache`/`security_cache` и in-memory кэш;
IaC-отчёты не персистятся между перезапусками (парсинг локальных файлов
дёшев). `audit_log` для read-only запросов не пишется.

---

## 5. Технические ограничения и политика

| Параметр | Значение |
|----------|----------|
| Библиотека Git | **pygit2** для status/discovery/log/compare; shell `git` (subprocess) для fetch/rev-list |
| Fetch | `git fetch --all --prune`, таймаут 30 с; ошибка → `remote_status=unavailable` |
| Read-only | Операции чтения не изменяют рабочую директорию и индекс |
| Мутации | `fetch`/`pull`/`push`/`stash`/`push_mirror`/`commit` — только `POST .../actions/{action}` с `confirm=true` и аудитом `action_log` (commit — v0.7.0); `update-dependencies` — только §3.20 (v0.7.0) |
| Глубина сканирования | `SCAN_DEPTH` (default 3) |
| Исключения сканирования | `.git`, `node_modules`, `.venv`, `vendor`, `dist`, `build`, `target` |
| Параллелизм сканирования | `SCAN_CONCURRENCY` (default 4) |
| Кэш локального статуса | `STATUS_TTL_SECONDS` (default 60) |
| **Кэш compare** | **`COMPARE_TTL_SECONDS` (default 60; ключ `repo_id, base, head`)** |
| **Кэш mirror-статуса** | **`MIRROR_STATUS_TTL_SECONDS` (default 300)** |
| **Интервал polling** | **`MIRROR_POLL_INTERVAL_SECONDS` (default 300; замедление при rate-limit)** |
| **Webhook secret** | **`WEBHOOK_SECRET` (опционально, HMAC-валидация)** |
| **Токены провайдеров** | **`GITHUB_TOKEN`, `GITFLIC_TOKEN` (обязательны для mirror; без них `mirror_status=unavailable`, `mirror_expected` не влияет на UI-шум)** |
| **Docker** | **`DOCKER_ENABLED` (default true), `DOCKER_HOST` (SDK default: UDS/npipe; в compose — `unix:///var/run/docker.sock`), `DOCKER_PATH_MAP` (host→container, например `C:/Projects=/projects`), `DOCKER_STATUS_TTL_SECONDS` (default 30), `DOCKER_TIMEOUT_SECONDS` (default 3); только `GET`-операции** |
| **Dependency checks** | **`DEPENDENCY_CACHE_TTL_SECONDS` (default 86400), `DEPENDENCY_CHECK_CONCURRENCY` (default 4), `DEPENDENCY_HTTP_TIMEOUT` (default 5 с); манифесты — `requirements.txt` (Python, Sprint 25), `package.json` (Node, Sprint 26) и `*.csproj`/`Directory.Packages.props`/`packages.config` (.NET, реализовано в Sprint 57); MSBuild не вычисляется** |
| **Security (v0.6.0)** | **`OSV_API_URL` (default `https://api.osv.dev`), `SECURITY_CACHE_TTL_SECONDS` (default 21600), `SECURITY_CHECK_CONCURRENCY` (default 4), `SECURITY_HTTP_TIMEOUT` (default 10 с); проверка только объявленных версий, `pip`/`npm` не запускаются** |
| **Secret scanning (v0.6.0)** | **`SECRET_SCAN_ENABLED` (default true), `SECRET_SCAN_MAX_FILES` (default 5000), `SECRET_SCAN_MAX_FILE_BYTES` (default 1048576), `SECRET_SCAN_TTL_SECONDS` (default 300); только рабочая директория, история Git не сканируется** |
| **Insights (v0.6.0)** | **`INSIGHTS_CACHE_TTL_SECONDS` (default 300), `INSIGHTS_GIT_TIMEOUT_SECONDS` (default 10), `INSIGHTS_HOTSPOTS_LIMIT` (default 5), `INSIGHTS_HOTSPOTS_DAYS` (default 90); только `git log`/`git rev-parse`, без fetch** |
| **LLM / AI (v0.7.0)** | **`LLM_ENABLED` (default false), `LLM_BASE_URL` (default `http://127.0.0.1:1234/v1`), `LLM_MODEL` (default `qwen2.5-coder-7b-instruct`), `LLM_API_KEY` (опционально), `LLM_TIMEOUT_SECONDS` (default 30), `LLM_MAX_DIFF_CHARS` (default 10000), `LLM_ALLOW_REMOTE` (default false), `AI_CACHE_TTL_SECONDS` (default 604800); diff/промпты не логируются** |
| **Global analytics (v0.7.0)** | **`GLOBAL_ANALYTICS_CACHE_TTL_SECONDS` (default 3600), `GLOBAL_ANALYTICS_LIMIT` (default 50), `GLOBAL_ANALYTICS_CONCURRENCY` (default 4); агрегация через `DependencyService` + `dependency_cache`, `refresh=true` обходит кэш** |
| **Dependency updates (v0.7.0)** | **`DEPENDENCY_UPDATE_TIMEOUT_SECONDS` (default 180), `DEPENDENCY_UPDATE_MAX_OUTPUT_CHARS` (default 10000); только `confirm=true` + чистый worktree (`git status --porcelain`) + `action_log`** |
| **.NET toolchain (v1.3.0, реализовано)** | **`*.csproj`/`Directory.Packages.props` парсятся stdlib XML без DTD/сущностей; `dotnet` CLI опционален; `dotnet list --outdated --no-restore`, затем `dotnet add <project> package <id> --no-restore` — только §3.20; `restore/build/publish` запрещены** |
| **Team & audit (v1.3.0, реализовано)** | **`users.role ∈ {admin, auditor}` (default `auditor`, bootstrap — `admin`); `require_admin` на мутациях; `audit_log` append-only, admin-only; секреты/содержимое файлов не пишутся** |
| **SAST (v1.3.0, реализовано)** | **`SAST_ENABLED` (default true), `SAST_TIMEOUT_SECONDS` (default 120), `SAST_MAX_FINDINGS` (default 500), `SAST_MAX_OUTPUT_BYTES` (8 MiB), `SAST_CACHE_TTL_SECONDS` (default 86400), `SAST_SEMGREP_CONFIG` (локальные правила); bandit/semgrep/eslint опциональны, сеть и `--config auto` запрещены** |
| **Automation configs (v1.3.0, реализовано)** | **`POST /repositories/{id}/automation/generate` только возвращает текст Dependabot/Renovate; файлы не пишутся, commit/push не выполняются** |
| **Global stats (v1.5.0, план)** | **`GLOBAL_STATS_CACHE_TTL_SECONDS` (default 300), `GLOBAL_STATS_CONCURRENCY` (default 4), `GLOBAL_STATS_TOP_LIMIT` (default 5); агрегация только по `tracked=true`, источники — существующие кэши, single-flight, `refresh=true` обходит кэш; AI-совет через `ai_cache`, промпт без кода/секретов** |
| **IaC scanning (v1.5.0, план)** | **`IAC_ENABLED` (default true), `IAC_MAX_DEPTH` (default 3), `IAC_MAX_FILES` (default 100), `IAC_MAX_FILE_BYTES` (default 1048576), `IAC_MAX_FINDINGS` (default 200), `IAC_TIMEOUT_SECONDS` (default 10), `IAC_CACHE_TTL_SECONDS` (default 300), `IAC_CONCURRENCY` (default 4), `GLOBAL_IAC_CACHE_TTL_SECONDS` (default 300), `IAC_GLOBAL_TOP_LIMIT` (default 10); Docker daemon/registry/сеть не используются, файлы только читаются** |
| **E2E и bundle (v0.9.0, реализовано)** | **Playwright (`@playwright/test`, dev-only), моки `page.route()`, dev-сервер 5173; entry bundle 89.85 kB gzip, budget-check без новой runtime-зависимости** |
| **Settings UI (v0.9.0, реализовано)** | **`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `NOTIFICATIONS_ENABLED`, `FETCH_TIMEOUT`, `STATUS_TTL_SECONDS`, `MIRROR_POLL_INTERVAL_SECONDS`; сид `app_settings` из `.env`; runtime-применение без перезапуска** |
| **GigaChat OAuth (v0.9.0, реализовано)** | **`GIGACHAT_OAUTH_URL` (default `https://ngw.devices.sberbank.ru:9443/api/v2/oauth`), `GIGACHAT_SCOPE` (default `GIGACHAT_API_PERS`), `GIGACHAT_CA_BUNDLE`, `GIGACHAT_TIMEOUT_SECONDS` (default 30), `GIGACHAT_TOKEN_REFRESH_MARGIN_SECONDS` (default 60); токен ~30 мин, секреты не логируются** |
| **Auth (v1.0.0, реализовано)** | **`AUTH_ENABLED` (default true), `ADMIN_USERNAME` (default `admin`), `ADMIN_PASSWORD` (default `admin`, хэшируется при bootstrap), `AUTH_JWT_SECRET` (≥32 байта), `AUTH_TOKEN_TTL_SECONDS` (default 604800 — 7 дней), `AUTH_LOGIN_RATE_LIMIT` (default 5), `AUTH_LOGIN_RATE_WINDOW_SECONDS` (default 60); cookie `iiruchating_session` HttpOnly/SameSite=Lax** |
| **Desktop (v1.0.0, реализовано)** | **`TAURI_MODE=true` (sidecar) → SQLite в `TAURI_DATA_DIR`/AppData, `SCAN_ROOTS` по умолчанию `~/Projects`; `backend.log` в app-data; RAG только внешний PostgreSQL** |
| **Smart AI cache (v0.9.0, реализовано)** | **`AI_PROMPT_VERSION` (default `v1`), state hash в ключе `ai_cache`, single-flight, `X-AI-Cache: hit\|miss`; `refresh=true` обходит кэш; ошибки LLM не кэшируются** |
| **RAG (v0.9.0; SQLite v1.4.0)** | **PostgreSQL + `pgvector` или SQLite + `sqlite-vec`; модель — `embedding_model` активного профиля (fallback `EMBEDDING_MODEL`, default `text-embedding-3-small`), `EMBEDDING_BASE_URL`, `EMBEDDING_DIMENSIONS` (default 1536; для `nomic-embed-text` — 768), `EMBEDDING_ALLOW_REMOTE` (default false), `EMBEDDING_BATCH_SIZE` (default 32), `RAG_MAX_FILE_BYTES` (524288), `RAG_MAX_CHUNKS_PER_REPO` (2000), `RAG_CHUNK_CHARS` (1000), `RAG_CHUNK_OVERLAP` (150); пустая модель → `503 embedding_model_not_configured`** |

---

## 6. Критерии приёмки

### 6.1. Базовые (v0.1.0–v0.4.0, выполнено)

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

### 6.2. v0.5.0 (выполнено)

- [x] Docker: `GET /repositories/{id}/docker` возвращает контейнеры проекта,
      порты и health; `status ∈ {running, stopped, not_found, unavailable}`,
      недоступный Docker → `status=unavailable`, без 5xx.
- [x] Docker read-only: в коде нет start/stop/restart/exec/logs; сокет
      монтируется `:ro`; проверка grep-аудитом.
- [x] Charts: recharts использует M3-токены, графики читаемы в light/dark,
      контраст WCAG AA.
- [x] Python: `requirements.txt` парсится (pins/ranges/includes/markers),
      устаревшие пакеты выводятся в карточке.
- [x] Node: `package.json` (`dependencies`/`devDependencies`) парсится,
      scoped/ignored/ranges классифицируются корректно.
- [x] Кэш зависимостей: TTL 24 ч, переживает перезапуск, rate-limit → partial/
      `unavailable`, без 5xx.
- [x] Тесты: манифесты на реальных tmp-репозиториях; PyPI/npm — на fake-клиентах.
- [x] Релиз: docs-consistency audit, тег `v0.5.0` в GitHub и GitFlic, `SHA(main)`
      совпадает.

### 6.3. v0.6.0 (выполнено, спринты 27–30)

- [x] Security: `GET /repositories/{id}/security` возвращает `SecurityReport`
      по §3.16; Python и Node проверяются через OSV.dev.
- [x] Security: exact-версии дают CVE, диапазоны помечаются `lower_bound`,
      неразрешимые — `unknown_packages`; по умолчанию видны High/Critical.
- [x] Security: OSV 429/5xx/timeout → `unavailable`/partial, HTTP 200; кэш 6 ч
      переживает перезапуск.
- [x] Secrets: сканируется рабочая директория (tracked + untracked non-ignored),
      история Git — нет; в ответе только masked preview.
- [x] Secrets: лимиты файлов/размера соблюдаются; `# iiruchating:ignore-secret`
      и `include_secrets=false` работают.
- [x] Insights: `GET /repositories/{id}/insights` возвращает топ-5 hotspots и
      commit frequency по §3.17; Git-вызовы не блокируют event loop.
- [x] Insights: timeout ≤ 10 с, кэш 300 с, `refresh=true`; пустая история и
      shallow clone дают статус, а не 500.
- [x] Read-only: нет установки/обновления пакетов, fetch/checkout/reset и
      записи в репозиторий (grep-аудит); секреты не попадают в логи и диффы.
- [x] Collaboration: Markdown-сводка копируется и отражает фильтры;
      export/import workspace сохраняет views и колонки, не экспортирует токены.
- [x] Релиз: docs-consistency audit, тег `v0.6.0` в GitHub и GitFlic,
      `SHA(main)` совпадает.

### 6.4. v0.7.0 (выполнено, спринты 32–34)

- [x] AI: `POST /repositories/{id}/ai/commit-message` возвращает
      `CommitMessageSuggestion` по §3.18.1; `400` без изменений, `409` при
      выключенном LLM/remote, `503` при недоступной LLM.
- [x] AI: diff ограничен `LLM_MAX_DIFF_CHARS` и помечается `[diff truncated]`;
      бинарники не дают текстового diff; diff, промпты и `llm_api_key` не
      попадают в логи/БД.
- [x] AI: не-loopback endpoint блокируется без `LLM_ALLOW_REMOTE=true`;
      сообщение показывается в редактируемой модалке и не коммитится само.
- [x] AI: `POST /repositories/{id}/ai/cve-explain` возвращает объяснение LLM,
      кэшируется в `ai_cache` на 7 дней; `409` при выключенном LLM/remote,
      `503` при недоступной LLM.
- [x] Global: `GET /dashboard/global-dependencies` агрегирует tracked-репозитории,
      считает `distribution`/`unification_needed` и кэшируется на 1 час.
- [x] Updates: обновление пакетов невозможно без `confirm=true` и на грязном
      worktree (`409 "Worktree must be clean"`); каждая попытка пишется в
      `action_log`.
- [x] Updates: timeout ≤ 180 с, вывод ограничен 10000 символов и очищен от
      токенов; bulk обновляет выбранные репозитории с concurrency 2.
- [x] Read-only: AI и global analytics не меняют репозиторий; обновления — только
      через §3.20 (grep-аудит destructive-команд).
- [x] UI: модалки commit/CVE, глобальная таблица, подтверждение обновления
      пакетов; пустые/частичные состояния.
- [x] Релиз: docs-consistency audit, тег `v0.7.0` в GitHub и GitFlic,
      `SHA(main)` совпадает.

### 6.5. v0.8.0 (выполнено, спринты 35–40)

- [x] Dependencies: `ManifestDiscovery` находит вложенные
      `requirements.txt`/`package.json`; `manifests[]` и `manifest_path`
      присутствуют в отчёте; `node_modules`/`.venv` игнорируются.
- [x] README/docs: `GET /repositories/{id}/readme` и
      `GET /repositories/{id}/docs?path=...` отдают только безопасные
      документы (≤ 512 KiB, внутри корня, без `.git`); UI-модалка с историей.
- [x] Dashboard: рекомендации выше вторичных секций; после действия статус,
      рекомендации, коммиты, зеркало и история обновляются последовательно.
- [x] UX/i18n: RU/EN без перезагрузки и с сохранением в `localStorage`;
      кликабельные карточки сводки; сворачиваемые фильтры/аналитика.
- [x] Duplicates: `GET /dashboard/duplicates` группирует клоны по remote URL;
      блок «Унификация» и AI-совет не выдумывают версии.
- [x] AI: `POST /ai/dashboard-advice`, `POST /repositories/{id}/ai/agent-task`,
      `POST /settings/llm/test`; задача для агента не выполняется автоматически.
- [x] Providers: `GET/POST/PATCH/DELETE /settings/ai-providers` и `activate`;
      ключи маскируются; активный профиль переключается без перезапуска.
- [x] Релиз: версии `0.8.0`, CHANGELOG/RELEASES/README/SPEC/ARCHITECTURE
      согласованы; `ruff`/`mypy`/`pytest`/frontend-проверки зелёные.

### 6.6. v0.9.0 (реализовано, спринты 42–44)

- [x] E2E: Playwright, 3 сценария (onboarding→scan→dashboard, RU/EN+тема,
      AI-коммит с мок-LLM) на изолированных tmp-репозиториях; 0 flaky.
- [x] Bundle: entry **< 90 kB gzip**; словари `settings`/`repository` — в
      lazy-чанках; budget-check падает при превышении.
- [x] GigaChat: `POST /api/v1/settings/ai-providers/gigachat/auth` выполняет
      OAuth 2.0, не возвращает токен/секрет; refresh автоматический,
      `401` обрабатывается; KI-018.
- [x] Smart cache: повторный запрос при неизменном состоянии → `cached=true`,
      LLM не вызывается; изменение состояния/`refresh=true` → вызов;
      ошибки не кэшируются.
- [x] RAG: `POST /api/v1/search/code` ищет по README/docs/src всех tracked
      проектов; индексация инкрементальна и не меняет репозитории; на SQLite —
      `503 rag_unavailable`; KI-017.
- [x] Релиз: версии `0.9.0`, CHANGELOG/RELEASES/SPEC/ARCHITECTURE/README
      согласованы; тег и зеркало GitFlic совпадают по SHA.

### 6.7. v1.0.0 (план, спринты 47–49)

- [ ] Auth: `POST /auth/login`, JWT + httpOnly cookie, middleware защищает все
      роуты кроме `/health`, `/metrics`, `/auth/login`; один пользователь,
      bcrypt, rate-limit.
- [ ] Desktop: Tauri + Python sidecar, автоматический старт/остановка backend,
      Windows/macOS установщики, работа без Docker.
- [ ] Release: аудит безопасности, артефакты, `v1.0.0`, GitHub Release и
      GitFlic mirror.
- [ ] Документы: ADR-0016/0017, KI-019/KI-020, `TODO_V1.0.md`.

### 6.8. v1.3.0 (спринты 57–59 — реализовано)

- [x] .NET (Sprint 57): парсинг `.csproj`/`Directory.Packages.props`/
      `packages.config`, NuGet latest, CVE через OSV (`NuGet`), третья вкладка
      UI, обновление через `dotnet add --no-restore`, `.cs`/`.csproj` в
      hotspots и RAG.
- [x] Team (Sprint 58): роли `admin`/`auditor`, серверная проверка прав,
      CRUD пользователей, все мутации — `403` для auditor.
- [x] Audit Log (Sprint 58): append-only `audit_log`, admin-only API
      `GET /audit` с пагинацией, санитизация `details`.
- [x] SAST (Sprint 59): bandit + semgrep/eslint fallback,
      `GET /repositories/{id}/sast`, кэш 24 ч, лимиты, read-only, блок SAST.
- [x] Automated PRs (Sprint 59): generate Dependabot/Renovate, предпросмотр,
      отсутствие commit/push.
- [x] Release: версии `1.3.0`, CHANGELOG/RELEASES/README/SPEC/ARCHITECTURE,
      тег `v1.3.0`, артефакты Windows/macOS/Linux, KI-025 актуальна/закрыта.
- [x] Документы: ADR-0018–0021, `TODO_V1.3.0.md`.

### 6.9. v1.5.0 (спринты 63–65 — план)

- [ ] Global stats (Sprint 63): `GET /dashboard/global-stats`, агрегация
      outdated/CVE/dirty/diverged по `tracked=true`, partial/stale, кэш 5 мин,
      `top_problematic` и `problem_score`.
- [ ] AI Insights (Sprint 63): общий отчёт по кодовой базе через `ai_cache`,
      только агрегаты, 503 при LLM off, до 5 приоритетов.
- [ ] UI (Sprint 63): блок «Tech Debt Overview» с Pie/Bar (lazy), empty/partial/
      error, RU/EN, `aria`, entry bundle < 90 kB gzip.
- [ ] IaC (Sprint 64): `IacService` для `Dockerfile`/`docker-compose.yml`,
      правила IAC001–IAC008, `GET /repositories/{id}/iac`, лимиты, read-only.
- [ ] Global IaC (Sprint 64): `GET /dashboard/global-iac`, сводка на дашборде,
      `iac_issues` в global-stats.
- [ ] Release (Sprint 65): версии `1.5.0`, CHANGELOG/RELEASES/README/SPEC/
      ARCHITECTURE, тег `v1.5.0`, артефакты, KI-026 актуальна/закрыта.
- [ ] Документы: ADR-0023/0024, `TODO_V1.5.0.md`.

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
| OSV.dev API | v1 (`POST /v1/query`, `POST /v1/querybatch`) — v0.6.0 |
| NuGet V3 flat container | `api.nuget.org/v3-flatcontainer` — v1.3.0 (Sprint 57, реализовано) |
| .NET SDK / CLI | 8.0+ (опционально, только для обновления пакетов) — v1.3.0 (Sprint 57) |
| bandit / semgrep | 1.7+ / 1.x (внешние опциональные бинарники) — v1.3.0 |
| OpenAI-compatible LLM API | Ollama / LM Studio `/v1/chat/completions` — v0.7.0 |
| OpenAI-compatible Embeddings API | Ollama / LM Studio `/v1/embeddings` — v0.9.0 (план) |
| GigaChat OAuth 2.0 | `https://ngw.devices.sberbank.ru:9443/api/v2/oauth` — v0.9.0 (план) |
| PostgreSQL + pgvector | PostgreSQL 17 + `pgvector` 0.7+ — v0.9.0 (план) |
| Playwright | `@playwright/test` (dev-only) — v0.9.0 (план) |
| SQLite / PostgreSQL | 3.45+ / 17 |
| Docker SDK (docker-py) | 7.1.0 (Docker Engine API 1.40+) |
| React / Vite / TypeScript | 19 / 8 / 7 |

---

## 8. Roadmap

| Версия | Фокус | Документ |
|--------|-------|----------|
| v0.4.0 | UX/UI, advanced table, saved views, command palette, a11y, Telegram, heatmap, export | `TODO_V0.4.md` |
| v0.5.0 | тёмные графики M3, Docker-интеграция, зависимости Python/Node | `TODO_V0.5.md` |
| v0.6.0 | supply-chain security (CVE, secrets), hotspots/DORA-lite, Markdown/workspace export | `TODO_V0.6.md` |
| v0.7.0 | локальный LLM (commit message, CVE explain), global dependencies, обновление пакетов | `TODO_V0.7.md` |
| v0.8.0 | вложенные манифесты, README/docs, RU/EN, дубли, AI-рекомендации, профили провайдеров | `TODO_V0.8.md` |
| v0.9.0 (план) | E2E Playwright, bundle < 90 kB gzip, GigaChat OAuth, smart AI cache, RAG на pgvector | `TODO_V0.9.md` |
| v0.9.0+ | синхронизация представлений, история статусов, расширенные интеграции | `TODO.md` |
| v1.0.0 | single-user auth (JWT), Tauri desktop, PostgreSQL + pgvector | `TODO_V1.0.md` |
| v1.1.0 | onboarding, файловые логи, автообновления Tauri, GitHub Actions | — |
| v1.2.0 | AI code review, conflict resolver, release notes, conversational RAG, кросс-платформенный релиз | `TODO_V1.2.0.md` |
| v1.3.0 | .NET/NuGet, Team Edition (роли, audit log), SAST, автоматические PR | `TODO_V1.3.0.md` |
| v1.4.0 | RAG на SQLite + `sqlite-vec` для desktop, Python-fallback, UX-фиксы | `docs/CHANGELOG.md` |
| v1.4.1 | смена своего пароля, admin-сброс пароля | `docs/CHANGELOG.md` |
| v1.4.2 | `chat_model`/`embedding_model` в профиле AI, отдельная проверка эмбеддингов, миграция 016 | `docs/CHANGELOG.md` |
| v1.5.0 (план) | Global Tech Debt Dashboard, AI-отчёт по всей базе, IaC Scanning (`Dockerfile`/compose), global-iac | `TODO_V1.5.0.md` |

---

## 9. UX/UI Guidelines

**Статус:** v0.4.0 — реализовано (спринты 18–21); разделы 9.8–9.9 — v0.5.0
(реализовано), разделы 9.10–9.11 — v0.6.0 (реализовано), раздел 9.12 —
v0.7.0 (Sprints 32–34), раздел 9.13 — v0.8.0 (Sprints 35–39), раздел 9.14 —
v0.9.0 (план, Sprints 42–44), раздел 9.15 — v1.3.0 (Sprints 57–59).

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
- **Не реализовано (вне scope v0.5.0):** опциональные колонки «Docker»
  (running/exited/off) и «Зависимости» (число устаревших); column manager
  поддерживает их добавление в v0.7+.

### 9.2 Фильтры и сохранённые представления

- Фильтры представлены чипами: статус, canonical provider, `mirror_status`,
  tracked, stale; активные чипы видны всегда, есть «Очистить всё».
- **Saved view** = `{name, filters, sorting, visible_columns}`.
- Версионированная схема (`version: 1`); несовместимые версии мигрируются или
  сбрасываются с уведомлением. v0.4.0–v0.8.0 — localStorage (+ файловый
  export/import workspace); синхронизация в БД — кандидат v0.9.1+ (в v0.8.0
  не входила).
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

### 9.8 Тёмные графики (v0.5.0, реализовано)

- Все элементы recharts (оси, сетка, легенда, тултип, серии) используют
  семантические токены `--chart-*`; хардкод hex в компонентах не допускается.
- Light/dark переключаются без перезагрузки; tooltip — surface-container/on-surface,
  сетка и оси — outline-variant/on-surface-variant.
- Контраст текста и линий ≥ 4.5:1 (графические линии — ≥ 3:1); цвет не единственный
  носитель смысла — подписи/легенда дублируют категорию.
- Пустые данные показывают текстовое состояние, а не пустой SVG.
- Тяжёлые чарты остаются lazy; переключение темы не вызывает reflow всей таблицы.

### 9.9 Docker и зависимости (v0.5.0, реализовано)

**Docker:**

- В карточке/деталях: бейдж состояния, health, image, compose service, порты.
- `status=unavailable` → «Docker недоступен» + ссылка на KI-009; блок не ломает карточку.
- Только просмотр; кнопок start/stop/restart/logs нет.
- «Обновить» вызывает `?refresh=true`.

**Зависимости:**

- Группировка по ecosystem (Python/Node), счётчики `outdated / up_to_date / unknown / ignored`.
- Строка пакета: имя, `declared` → `latest`, severity-бейдж, ссылка на registry.
- Partial failure: ошибка одного ecosystem не скрывает другой.
- Кнопка «Проверить снова» → `?refresh=true`; автоматического обновления пакетов нет.
- Блоки lazy; счётчик в карточке не требует раскрытия списка.

### 9.10 Security и Insights (v0.6.0; Sprint 28–29)

**Security:**

- Блок «Безопасность» в деталях/карточке: счётчики `critical / high / medium /
  low / unknown`, список уязвимостей (пакет, версия, severity-бейдж,
  CVE/GHSA-ссылка, `fixed_version`).
- `version_source=lower_bound` показывается пометкой «диапазон» — результат
  приблизительный; `unknown_packages` — отдельным списком, не «чисто».
- Секреты: `file:line`, тип, severity и **маскированный** preview; полное
  значение не показывается и не копируется.
- Состояния `no_manifest`, `unavailable`, `partial`, `truncated` читаемы и не
  ломают карточку; только просмотр, кнопок «исправить/обновить пакет» нет.
- Цвет — не единственный носитель смысла: severity-бейджи имеют текстовую
  подпись; контраст AA в обеих темах.

**Insights:**

- Топ-5 «горячих» файлов: путь (mono, обрезка + tooltip), `changes`,
  относительная полоса; подпись «кандидаты на рефакторинг».
- Sparkline commit frequency за окно + подпись «за N дней, прокси DORA».
- `no_branch` / `shallow_clone` / `timeout` — отдельные состояния с пояснением,
  а не пустой график.
- Оба блока lazy, не участвуют в первичном `/dashboard`, кнопка «Обновить» →
  `?refresh=true`.

### 9.11 Collaboration: Markdown и Workspace export (v0.6.0, Sprint 30)

- **Markdown Export:** кнопка «Скопировать сводку» на дашборде. Сводка
  формируется на клиенте из текущего среза: заголовок с датой, счётчики
  `summary`, список «Проблемные проекты» (state, ahead/behind, mirror-статус).
  Markdown-спецсимволы в именах и backtick в путях экранируются; HTML не
  генерируется. Копирование в clipboard + toast, серверный эндпоинт не нужен.
- **Workspace Export/Import:** JSON-файл `{version: 1, exported_at, app_version,
  views, table: {visible_columns, column_widths}}`; имя файла
  `iiruchating_workspace.json`. Импорт — с проверкой размера (≤ 1 MiB), схемы и
  версии. Несовместимая версия/битый JSON → ошибка без изменения состояния.
  Применение — `replace` (текущее поведение; merge не поддерживается).
- В экспорт **не** попадают токены, секреты, `SCAN_ROOTS`, содержимое
  репозиториев и данные security/insights.
- Импорт не затрагивает `localStorage`-ключи других версий; после импорта
  store обновляется реактивно, без перезагрузки.

### 9.12 AI, глобальные зависимости и обновления (v0.7.0, Sprints 32–34)

**AI / LLM (commit и CVE — реализовано):**

- Settings: секция «AI / LLM» (enabled, endpoint, model, API key, timeout,
  max diff, `allow_remote`), маскировка ключа.
- Предупреждение, если endpoint не loopback: код проекта может быть отправлен
  на внешний сервис; без явного `allow_remote` запрос блокируется.
- Кнопка «Сгенерировать коммит» видна только при `dirty` и `llm_enabled`;
  открывает модалку с лоадером и редактируемым `<textarea>`, кнопками
  «Скопировать» и «Выполнить коммит» (только после явного чекбокса).
  Автоматического `git commit` нет.
- Ошибки LLM показываются toast «LLM недоступна. Проверьте настройки.»,
  не ломая карточку; diff-обрезка отражается предупреждением в модалке.
- В блоке «Безопасность» у уязвимости — «Объяснить» (при `llm_enabled`):
  модалка с лоадером и текстом объяснения, ошибка LLM — в той же модалке.
  Кнопка использует `CVE-*` (или `osv_id`), если CVE нет.

**Global dependencies:**

- Блок «Global Dependencies» на дашборде: таблица пакетов, ecosystem,
  `latest_version`, распределение версий (с проектами в tooltip), число
  проектов и бейдж «Унифицировать» при `unification_needed`.
- Счётчики `summary` (пакеты/репозитории/кандидаты); `refresh` — явная кнопка.
- Пустое состояние «Нет манифестов»; `partial_errors` — предупреждение.
- Серверный кэш 1 час, поэтому повторные рендеры дашборда не парсят 34 проекта.

**Dependency updates:**

- Кнопка «Обновить пакеты» в блоке «Зависимости» для выбранного ecosystem
  (Python/Node); disabled при `state="dirty"` и при отсутствии манифеста
  (tooltip «Закоммитьте изменения перед обновлением»).
- Модалка подтверждения: предупреждение об изменении `requirements.txt` /
  `package.json` и lock-файлов.
- После успеха — toast «Зависимости обновлены» + обновление статуса и отчёта
  зависимостей. Ошибка (dirty/manager/timeout) показывается в модалке.
- Никаких автозапусков и автоматических коммитов; все попытки — в `ActionLog`.
- Цвет — не единственный носитель смысла; модалки с `role="dialog"` и
  возвратом фокуса; блоки lazy, entry bundle в бюджете.

### 9.13 v0.8.0: README, i18n и AI-рекомендации (реализовано)

- README-модалка: безопасный Markdown, внутренние ссылки с историей «Назад»,
  внешние — в новой вкладке; лимит 512 KiB.
- RU/EN: переключатель в шапке, сохранение в `localStorage`
  (`iiruchating.locale`), `Intl` для дат/чисел, `document.lang`.
- Дашборд: кликабельные карточки сводки, сворачиваемые фильтры/аналитика,
  человеческие подписи состояний.
- AI: дайджест, модалка задачи для DSH/OpenCode и профили провайдеров
  грузятся lazy; ключи маскируются; remote — только opt-in.

### 9.14 v0.9.0 (план): поиск по коду, GigaChat и cache

- **Поиск по коду:** вход из Command Palette (`Ctrl+K` → «Найти код…») и
  отдельная панель; поле запроса, фильтры по проекту/языку, результаты с путём
  и строками, кнопки «Копировать путь»/«Открыть проект», `aria-live`.
- **GigaChat:** в модалке профиля — выбор GigaChat, поля client_id/secret/scope,
  кнопка «Авторизоваться», статус и срок действия токена; секреты маскируются.
- **Smart cache:** у AI-блоков — индикатор «из кэша» и время генерации.
- **Bundle:** `Settings` и `RepositoryDetails` грузят свои i18n-namespace
  лениво; entry < 90 kB gzip; E2E покрывает onboarding→scan→dashboard, RU/EN +
  тему и AI-коммит с мок-LLM.

### 9.15 v1.3.0: .NET, Team Edition и SAST

- **Зависимости:** третья вкладка «C# / .NET» с бейджем «CPM», путём
  манифеста и empty/error-состояниями; табы доступны с клавиатуры.
- **Безопасность (Sprint 59):** отдельный блок «Безопасность кода (SAST)» с
  находками bandit/semgrep/eslint, severity, `file:line`, сниппетом и кнопкой
  «Исправить с AI».
- **Автоматизация (Sprint 59):** lazy-модалка с генерацией Dependabot/Renovate,
  предпросмотром YAML/JSON и копированием; commit/push не выполняются.
- **Роли (Sprint 58):** ссылки «Команда»/«Аудит» видны только admin;
  `auditor` не может открыть `/admin/*` (редирект) и получает `403` на мутации.
- **Audit Log:** страница `/admin/audit` (admin, lazy): таблица
  дата/пользователь/действие/объект/детали, пагинация, `aria`, пустое
  состояние.
- **Автоматические PR:** блок в карточке репозитория с предпросмотром
  YAML/JSON, копированием и явным «Применить» (admin); предупреждение, что
  commit/push не выполняются.
