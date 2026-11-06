# SPEC — спецификация проекта (источник истины по контрактам)

Документ фиксирует **контракты** системы: API, схему БД, статусы, критерии приёмки.
Docker §3.14 реализован в Sprint 24; dependency §3.15 (Python/Node) — в Sprint 25–26;
Security §3.16 — в Sprint 28; Insights §3.17 — в Sprint 29.
AI §3.18, global analytics §3.19 и dependency updates §3.20 — **план v0.7.0**
(спринты 32–34); контракты зафиксированы до реализации.

**Версия:** v0.7.0 «AI & Global Analytics» (планирование) · **Обновлено:** 2026-11-06

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

**Вне области v0.1.0:** автоматический merge/rebase, CI-интеграция, мобильное приложение, мультипользовательский режим.

---

## 2. Роли

В v0.1.0 — **один пользователь** (владелец локальной машины). Аутентификация отсутствует (bind на `127.0.0.1`). Провайдеры GitHub/GitFlic авторизуются персональными токенами (`GITHUB_TOKEN`, `GITFLIC_TOKEN`), хранятся в `.env`. LLM API key (если нужен) хранится в `app_settings`, маскируется в API и не экспортируется.

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

`repositories[]` включает последний `status`, `mirror` и `ci` (`{github, gitflic, aggregate}`);
CI-статусы кэшируются (60 с) и не блокируют загрузку дашборда.

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

### 3.9. Actions — явные мутации (v0.2.0, ADR-0003)

Автоматических мутаций нет: действие выполняется только при `confirm=true` и
всегда попадает в `action_log`.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/repositories/{id}/actions/{action}` | `{confirm: true}` | `ActionLog` |
| POST | `/repositories/{id}/actions/update-dependencies` | `{confirm: true, ecosystem?, packages?}` | `ActionLog` (v0.7.0, план) |
| POST | `/mirror/actions/{action}` | `{confirm: true, repository_id}` | `ActionLog` |
| GET | `/admin/actions` | `repository_id?`, `limit?` | `ActionLog[]` |

- `action ∈ {pull, push, stash}`; `mirror action = push-mirror`.
- Без `confirm=true` → 400; неизвестное действие → 400.
- `update-dependencies` (v0.7.0) — отдельное действие Sprint 34; требует чистого
  worktree (`409 dirty_worktree`), пишет `action_log` даже при отказе/ошибке.
  Детали — §3.20.
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
| POST | `/repositories/actions/update_dependencies_all` | `{repo_ids?}`, `ecosystem?`, body `{confirm:true}` | `202 {status:"accepted"}` (v0.7.0, план) |

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
| GET | `/settings` | `{scan_roots, github_token, gitflic_token, webhook_secret, default_canonical_provider, llm_enabled, llm_base_url, llm_model, llm_api_key, llm_timeout_seconds, llm_allow_remote}` |
| PATCH | `/settings` | те же поля (все опциональны) → обновлённые значения |

Токены, `webhook_secret` и `llm_api_key` в ответе **маскируются**
(`ghp_****1234`, `sk-****1234`). Разрешённые ключи: `scan_roots`,
`github_token`, `gitflic_token`, `webhook_secret`, `default_canonical_provider`,
`llm_enabled`, `llm_base_url`, `llm_model`, `llm_api_key`,
`llm_timeout_seconds`, `llm_allow_remote`. Значения хранятся в `app_settings`;
при старте подхватываются в конфиг (fallback — `config.py`).

**LLM-настройки (v0.7.0, план):**

- `llm_enabled` (default **false**) — AI-функции выключены до явного включения.
- `llm_base_url` (default `http://127.0.0.1:11434/v1`) — Ollama; LM Studio —
  `http://127.0.0.1:1234/v1`.
- `llm_model` (default `qwen2.5-coder:7b`).
- `llm_api_key` — опционально; для локальных серверов обычно пустой.
- `llm_timeout_seconds` (default 30).
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

### 3.15. Dependency management (v0.5.0, Sprint 25–26)

Проверка объявленных зависимостей по манифестам в корне репозитория.
Файлы только читаются; в рамках проверки зависимостей `pip`/`npm`/`pnpm`
не запускаются (обновление пакетов — отдельное действие §3.20).

**Статус реализации:** Python (`requirements.txt`, PyPI) — Sprint 25;
Node (`package.json`, npm) — Sprint 26. `ecosystem=all` (или отсутствие
параметра) возвращает объединённый отчёт.

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/repositories/{id}/dependencies` | `refresh?: bool`, `ecosystem?: python\|node\|all` | `DependencyReport` |

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
      "manifest": "requirements.txt",
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
          "manifest_section": null
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

- `ecosystems` содержит запрошенные ecosystem (по умолчанию оба); отсутствующий
  манифест — запись `status=no_manifest`, а не 404/500.
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
- `declared` сохраняет исходное объявление; extras, environment markers и hashes
  не участвуют в сравнении.
- `manifest_line` — 1-based строка для `requirements.txt`; для `package.json`
  `null`. `manifest_section` — `dependencies`/`devDependencies` для Node, иначе
  `null`.
- `severity` считается по первой различающейся части версии (major/minor/patch)
  от `current` к `latest`.
- Транзитивные зависимости и lock-файлы **не** анализируются.

**Кэш:** `DEPENDENCY_CACHE_TTL_SECONDS` (default 86400 = 24 ч), ключ
`<registry>:<normalized-name>`, таблица `dependency_cache` (переживает
перезапуск). `refresh=true` обходит TTL для запрошенного репозитория и
обновляет кэш. При ошибке реестра отдаётся stale-кэш с `source=stale_cache`,
если он есть.

**Rate limits и ошибки:** concurrency ≤ `DEPENDENCY_CHECK_CONCURRENCY` (default 4),
timeout `DEPENDENCY_HTTP_TIMEOUT` (default 5 с), backoff на 429/5xx (0.5/1/2 с).
Ошибка одного пакета не скрывает остальные. `error` — строка: для registry-ошибок
используются коды `rate_limited`, `registry_unavailable`, `timeout`; для
`parse_error` — сообщение. Пакет, отсутствующий в реестре (404), получает
`latest=null`, `status=unknown`. При недоступном реестре и отсутствии кэша —
`ecosystem.status=unavailable`, HTTP 200 (частичный отчёт).

---

### 3.16. Security — CVE и Secret Scanning (v0.6.0, Sprint 28)

Проверка **объявленных** зависимостей на известные уязвимости через OSV.dev и
базовый поиск секретов в рабочей директории. Репозиторий только читается:
пакеты не устанавливаются/не обновляются, секреты не редактируются.

**Статус реализации:** Sprint 28 — реализовано (`SecurityService`,
`OsvClient`, `SecretScanner`).

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
      "manifest": "requirements.txt",
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
  - `exact` — версия из `==` / точного `package.json`;
  - `lower_bound` — нижняя граница диапазона (`>=`, `^`, `~` и т.п.);
    результат считается приблизительным и помечается в UI.
- Пакеты, для которых версию извлечь нельзя, попадают в `unknown_packages`
  (`reason ∈ {unresolved_range, unsupported_kind, registry_missing,
  osv_unavailable}`) и **не** считаются проверенными. `summary.unknown` — их
  количество.
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

- `security_cache`: ключ `osv:<ecosystem>:<package>:<version>`, TTL
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
    `poetry.lock`, `uv.lock`, `Cargo.lock`, `go.sum`, `*-lock.json`, `*.lock`);
  - generated/minified (`*.min.js`, `*.min.css`, `*.map`, `*.snap`);
  - каталоги `node_modules`, `.venv`, `venv`, `vendor`, `dist`, `build`,
    `target`, `__pycache__`, `.git`.
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

### 3.18. AI assistant (v0.7.0, Sprint 32–33, план)

Локальный LLM (Ollama / LM Studio) через OpenAI-совместимый API. Эндпоинты
**только читают** репозиторий и ничего не коммитят; результат — черновик,
который пользователь подтверждает вручную.

#### 3.18.1. Генерация commit message

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/repositories/{id}/ai/commit-message` | `{include_untracked?: bool, max_diff_bytes?: int}` | `CommitMessageSuggestion` |

`CommitMessageSuggestion`:

```json
{
  "repository_id": 1,
  "message": "feat(api): add repository security endpoint",
  "subject": "feat(api): add repository security endpoint",
  "body": null,
  "source": "llm",
  "provider": "ollama",
  "model": "qwen2.5-coder:7b",
  "truncated": false,
  "files_changed": 3,
  "warnings": [],
  "generated_at": "2026-11-06T10:00:00Z"
}
```

**Правила:**

- Требуется `dirty.modified + dirty.staged > 0`; иначе `422 no_changes`.
  Untracked-файлы по умолчанию не входят в diff (`include_untracked=false`).
- Источник diff: `git diff HEAD --no-color --no-ext-diff --unified=3`
  (staged + unstaged); бинарные файлы исключаются.
- `max_diff_bytes` (default **65536**, 1024..131072); при обрезке
  `truncated=true`, `warnings=["truncated_diff"]`. Обрезка — по границе файла.
- `llm_enabled=false` → `409 llm_disabled`; не-loopback endpoint без
  `llm_allow_remote=true` → `409 llm_remote_not_allowed`.
- Промпт: Conventional Commits, subject ≤ 72 символов, опциональное тело.
  Diff передаётся как данные; инструкции внутри diff игнорируются.
- Ответ валидируется regex
  `^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?: .+`;
  Markdown-обёртки снимаются. Невалидный/пустой ответ → fallback.
- Fallback (timeout/connection/5xx/невалидный ответ): `chore: update N files`
  с телом по группам файлов, `source="fallback"`, `provider=null`,
  `warnings=["llm_unavailable"]`; HTTP 200.
- Diff, промпт и ответ LLM **не** сохраняются в БД и не логируются (только
  метаданные: байты, модель, source, длительность).
- `source ∈ {llm, fallback}`; `provider ∈ {ollama, lmstudio, openai_compatible} | null`.

#### 3.18.2. Объяснение CVE

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/repositories/{id}/ai/cve-explain` | `{osv_id, package?, version?, locale?}` | `CveExplanation` |

`CveExplanation`:

```json
{
  "osv_id": "GHSA-9wx4-h78v-vm56",
  "package": "requests",
  "version": "2.19.0",
  "severity": "high",
  "fixed_version": "2.20.0",
  "explanation": "Уязвимость позволяет отправить учётные данные на чужой хост…",
  "source": "llm",
  "model": "qwen2.5-coder:7b",
  "cached": false,
  "references": ["https://github.com/advisories/GHSA-9wx4-h78v-vm56"],
  "generated_at": "2026-11-06T10:00:00Z"
}
```

**Правила:**

- Факты берутся из `security_cache` или `GET /v1/vulns/{osv_id}` OSV.dev;
  client-supplied `summary` не является единственным источником.
- `locale ∈ {ru, en}` (default **ru**); commit messages всегда английские.
- LLM получает только нормализованный advisory (id, summary, severity, affected,
  fixed, references) и обязан не выдумывать факты; ответ содержит ссылки.
- Кэш `ai_cache` (см. §4): ключ `cve-explain:<osv_id>:<locale>:<model>`,
  TTL `AI_CACHE_TTL_SECONDS` (default **604800** = 7 дней); `cached=true` при
  попадании.
- OSV недоступен и кэша нет → `503 osv_unavailable`; LLM недоступен →
  grounded-сводка из advisory, `source="fallback"`, HTTP 200.
- `llm_enabled=false` → `409 llm_disabled`; `404 advisory_not_found` — OSV не
  знает такой id.
- Объяснение не содержит полных секретов и не влияет на `SecurityReport`.

---

### 3.19. Global dependencies (v0.7.0, Sprint 33, план)

Сводка объявленных версий популярных пакетов по всем `tracked=true`
репозиториям. Только чтение; пакеты не обновляются.

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/dashboard/global-dependencies` | `ecosystem?: python\|node\|all`, `limit?: int (default 20, 1..100)`, `outdated_only?: bool`, `refresh?: bool` | `GlobalDependencyReport` |

`GlobalDependencyReport`:

```json
{
  "checked_at": "2026-11-06T10:00:00Z",
  "summary": {
    "repositories": 34,
    "repositories_with_manifests": 30,
    "packages": 120,
    "outdated_occurrences": 47,
    "unification_candidates": 8,
    "missing_latest": 3
  },
  "ecosystems": [
    {
      "ecosystem": "python",
      "repositories": 28,
      "packages": [
        {
          "name": "fastapi",
          "latest": "0.116.0",
          "repositories": 20,
          "outdated_repositories": 14,
          "versions": [
            {"version": "0.110.0", "repositories": 8},
            {"version": "0.115.6", "repositories": 6}
          ],
          "unification": "mixed",
          "recommended_version": "0.115.6",
          "status": "outdated"
        }
      ],
      "error": null
    }
  ],
  "error": null
}
```

**Правила:**

- Агрегация: `requirements.txt` + `package.json` (те же парсеры, что §3.15);
  пакеты без разрешимой версии попадают в `missing_latest`, а не в «current».
- `limit` — топ-N по числу репозиториев (`repositories` desc, `name` asc).
- `versions[]` — распределение declared-версий; `recommended_version` —
  максимальная declared-версия среди репозиториев (кандидат на унификацию),
  `latest` — последняя из registry-кэша.
- `unification ∈ {aligned, mixed, unknown}`: одна версия / ≥2 версий / нет
  разрешимых версий.
- `status ∈ {current, outdated, unknown}`: `current`, если
  `recommended_version >= latest`; `outdated`, если ниже; `unknown` без `latest`.
- `summary.outdated_occurrences` — число пар repo×package с устаревшей версией;
  `unification_candidates` — пакеты с `unification=mixed`.
- По умолчанию сетевых вызовов нет: `latest` берётся из `dependency_cache`.
  `refresh=true` обновляет stale-кэш через registry-клиенты (concurrency ≤ 4),
  partial failure отражается в `ecosystems[].error`, HTTP 200.
- In-memory кэш ответа 60 с; ключ `ecosystem + limit + outdated_only`.
- `outdated_only=true` возвращает только пакеты со `status=outdated`.

---

### 3.20. Automated dependency updates (v0.7.0, Sprint 34, план)

Явная мутация: обновление пакетов выбранного репозитория. Только при
`confirm=true`, на чистом worktree и с аудитом. Вне этого действия система
остаётся read-only.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/repositories/{id}/actions/update-dependencies` | `{confirm:true, ecosystem?: python\|node\|all, packages?: string[]}` | `ActionLog` |
| POST | `/repositories/actions/update_dependencies_all` | `{repo_ids?, ecosystem?}`, query/body `confirm=true` | `202 {status:"accepted"}` |

**Preflight:**

- `confirm != true` → `400 confirmation_required`.
- Worktree грязный (`state=dirty`, `dirty.modified/staged/conflicted > 0`) →
  `409 dirty_worktree`; действие не выполняется, но попытка пишется в
  `action_log` (`status=error`).
- Менеджер: Python — `requirements.txt` → `pip`; Node — `pnpm-lock.yaml` →
  `pnpm`, иначе `package-lock.json`/`package.json` → `npm`. Если манифеста нет
  для выбранного ecosystem → `409 no_manifest`.

**Команды:**

- Python (все): `pip install --upgrade -r requirements.txt`;
  выбранные: `pip install --upgrade <package>...`.
- Node (все): `pnpm update` / `npm update`;
  выбранные: `pnpm update <package>...` / `npm update <package>...`.
- Никаких `git`-мутаций, `--force`, `--legacy-peer-deps` и удаления lock-файлов.

**Ограничения и аудит:**

- Timeout `DEPENDENCY_UPDATE_TIMEOUT_SECONDS` (default **180**); по таймауту
  процесс убивается, `ActionLog.status=error`, `error=timeout`.
- Вывод ограничен 32 KiB; токены/credentials в URL редактируются
  (`https://****@host/...`) перед записью в `action_log`.
- `ActionLog`: `action="update-dependencies"`, `command`, `status`,
  `exit_code`, `output`, `error`, `duration_ms`, `actor=local|bulk`.
- Bulk: concurrency 1–2, `actor=bulk`; один упавший репозиторий не отменяет
  остальные.
- Обновление может изменить `package.json`/lockfile и окружение backend;
  UI обязан предупредить пользователя (KI-014). Автоматического коммита нет.
- ADR-0011 фиксирует preflight-политику и границы доверия.

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

dependency_cache(           -- v0.5.0
  key* TEXT PRIMARY KEY,    -- "pypi:fastapi" | "npm:react"
  ecosystem TEXT,           -- pypi | npm
  package TEXT,             -- нормализованное имя
  latest_version TEXT NULL,
  etag TEXT NULL,
  payload JSONB,            -- последний ответ реестра (нормализованный)
  checked_at
)

security_cache(             -- v0.6.0 (Sprint 28)
  key* TEXT PRIMARY KEY,    -- "osv:pypi:requests:2.19.0"
  ecosystem TEXT,           -- pypi | npm
  package TEXT,
  version TEXT,             -- проверяемая версия (exact или lower_bound)
  payload JSONB,            -- нормализованный ответ OSV.dev
  checked_at
)

ai_cache(                   -- v0.7.0 (план, Sprint 33)
  key* TEXT PRIMARY KEY,    -- "cve-explain:GHSA-...:ru:qwen2.5-coder:7b"
  kind TEXT,                -- cve_explain
  model TEXT NULL,
  payload JSONB,            -- {explanation, references, ...}
  checked_at
)
```

Индексы: `repositories(path)`, `repositories(tracked)`, `repositories(github_full_name)`, `repositories(gitflic_full_name)`, `repository_status(repository_id)`, `repository_mirror_status(repository_id)`, `scan_runs(started_at)`, `webhook_events(received_at)`, `webhook_events(provider, event_type)`, `dependency_cache(checked_at)`, `security_cache(checked_at)`, `ai_cache(checked_at)`.

---

## 5. Технические ограничения и политика

| Параметр | Значение |
|----------|----------|
| Библиотека Git | **pygit2** для status/discovery/log/compare; shell `git` (subprocess) для fetch/rev-list |
| Fetch | `git fetch --all --prune`, таймаут 30 с; ошибка → `remote_status=unavailable` |
| Read-only | Операции чтения не изменяют рабочую директорию и индекс |
| Мутации | `fetch`/`pull`/`push`/`stash`/`push_mirror` — только `POST .../actions/{action}` с `confirm=true` и аудитом `action_log` (v0.2.0); `update-dependencies` — только §3.20 (v0.7.0) |
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
| **Dependency checks** | **`DEPENDENCY_CACHE_TTL_SECONDS` (default 86400), `DEPENDENCY_CHECK_CONCURRENCY` (default 4), `DEPENDENCY_HTTP_TIMEOUT` (default 5 с); манифесты — `requirements.txt` (Python, Sprint 25) и `package.json` (Node, Sprint 26) в корне (+ относительные `-r` include)** |
| **Security (v0.6.0)** | **`OSV_API_URL` (default `https://api.osv.dev`), `SECURITY_CACHE_TTL_SECONDS` (default 21600), `SECURITY_CHECK_CONCURRENCY` (default 4), `SECURITY_HTTP_TIMEOUT` (default 10 с); проверка только объявленных версий, `pip`/`npm` не запускаются** |
| **Secret scanning (v0.6.0)** | **`SECRET_SCAN_ENABLED` (default true), `SECRET_SCAN_MAX_FILES` (default 5000), `SECRET_SCAN_MAX_FILE_BYTES` (default 1048576), `SECRET_SCAN_TTL_SECONDS` (default 300); только рабочая директория, история Git не сканируется** |
| **Insights (v0.6.0)** | **`INSIGHTS_CACHE_TTL_SECONDS` (default 300), `INSIGHTS_GIT_TIMEOUT_SECONDS` (default 10), `INSIGHTS_HOTSPOTS_LIMIT` (default 5), `INSIGHTS_HOTSPOTS_DAYS` (default 90); только `git log`/`git rev-parse`, без fetch** |
| **LLM / AI (v0.7.0)** | **`LLM_ENABLED` (default false), `LLM_BASE_URL` (default `http://127.0.0.1:11434/v1`), `LLM_MODEL` (default `qwen2.5-coder:7b`), `LLM_API_KEY` (опционально), `LLM_TIMEOUT_SECONDS` (default 30), `LLM_MAX_DIFF_BYTES` (default 65536), `LLM_ALLOW_REMOTE` (default false), `AI_CACHE_TTL_SECONDS` (default 604800); diff/промпты не логируются** |
| **Global analytics (v0.7.0)** | **`GLOBAL_ANALYTICS_CACHE_TTL_SECONDS` (default 60), `GLOBAL_ANALYTICS_LIMIT` (default 20); по умолчанию только `dependency_cache`, `refresh=true` — registry с concurrency ≤ 4** |
| **Dependency updates (v0.7.0)** | **`DEPENDENCY_UPDATE_TIMEOUT_SECONDS` (default 180), `DEPENDENCY_UPDATE_MAX_OUTPUT_BYTES` (default 32768); только `confirm=true` + чистый worktree + `action_log`** |

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

### 6.4. v0.7.0 (план, спринты 32–34)

- [ ] AI: `POST /repositories/{id}/ai/commit-message` возвращает
      `CommitMessageSuggestion` по §3.18.1; LLM timeout ≤ 30 с, ошибки →
      fallback, HTTP 200.
- [ ] AI: diff ограничен `LLM_MAX_DIFF_BYTES`, бинарники исключены; diff,
      промпты и `llm_api_key` не попадают в логи/БД.
- [ ] AI: не-loopback endpoint блокируется без `LLM_ALLOW_REMOTE=true`;
      сгенерированное сообщение валидно как Conventional Commits.
- [ ] AI: `POST /repositories/{id}/ai/cve-explain` опирается на OSV, кэшируется
      в `ai_cache` на 7 дней и не выдумывает `fixed_version`/ссылки.
- [ ] Global: `GET /dashboard/global-dependencies` агрегирует tracked-репозитории,
      считает `unification`/`recommended_version` и не делает N×registry
      запросов без `refresh=true`.
- [ ] Updates: обновление пакетов невозможно без `confirm=true` и на грязном
      worktree (`409 dirty_worktree`); каждая попытка пишется в `action_log`.
- [ ] Updates: timeout ≤ 180 с, вывод ограничен и очищен от токенов; bulk
      обновляет выбранные репозитории с concurrency 1–2.
- [ ] Read-only: AI и global analytics не меняют репозиторий; обновления — только
      через §3.20 (grep-аудит destructive-команд).
- [ ] UI: модалки commit/CVE, глобальный дашборд, подтверждение обновления;
      пустые/частичные состояния, lazy-загрузка.
- [ ] Релиз: docs-consistency audit, тег `v0.7.0` в GitHub и GitFlic,
      `SHA(main)` совпадает.

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
| OpenAI-compatible LLM API | Ollama / LM Studio `/v1/chat/completions` — v0.7.0 |
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
| v0.8.0+ | серверная синхронизация представлений, история статусов, расширенные интеграции | `TODO.md` |

---

## 9. UX/UI Guidelines

**Статус:** v0.4.0 — реализовано (спринты 18–21); разделы 9.8–9.9 — v0.5.0
(реализовано), разделы 9.10–9.11 — v0.6.0 (реализовано), раздел 9.12 —
план v0.7.0.

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
  сбрасываются с уведомлением. v0.4.0–v0.6.0 — localStorage (+ файловый
  export/import workspace); v0.7.0 — синхронизация в БД.
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

### 9.12 AI, глобальные зависимости и обновления (v0.7.0, план)

**AI / LLM:**

- Settings: секция «AI / LLM» (endpoint, model, API key, timeout,
  `allow_remote`), маскировка ключа, кнопка проверки соединения.
- Предупреждение, если endpoint не loopback: код проекта отправляется на
  внешний сервис; без явного `allow_remote` сохранение блокируется.
- Кнопка «Сгенерировать коммит» видна только при `dirty` и `llm_enabled`;
  открывает модалку с subject/body, `source`, `truncated`, кнопкой «Копировать».
  Автоматического `git commit` нет; сообщение можно отредактировать.
- В блоке «Безопасность» у уязвимости — «Объяснить»: модалка с лоадером,
  объяснением, `fixed_version`, ссылками и пометкой `cached`/`fallback`.
- Ошибки LLM показываются как состояние («LLM недоступен, показан черновик»),
  не ломая карточку; таймаут отменяем.

**Global dependencies:**

- Отдельная страница/секция: топ-N пакетов, число репозиториев, распределение
  версий, `recommended_version`, бейджи `aligned/mixed/outdated/unknown`.
- Фильтры ecosystem и «только устаревшие»; счётчики `summary`.
- `refresh` — явная кнопка; по умолчанию данные из кэша.
- Пустое состояние «Нет манифестов»; partial error по ecosystem.

**Dependency updates:**

- Кнопка «Обновить пакеты» для выбранных проектов; модалка с перечнем
  ecosystem/пакетов и предупреждением, что изменятся lockfile/окружение.
- При `dirty_worktree` — понятная ошибка, действие не выполняется.
- Прогресс/результат, ссылка на `ActionLog`; никаких автозапусков и
  автоматических коммитов.
- Цвет — не единственный носитель смысла; модалки с `role="dialog"` и
  возвратом фокуса; блоки lazy, entry bundle в бюджете.
