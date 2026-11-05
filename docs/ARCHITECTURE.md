# ARCHITECTURE — как устроен IIRuchating

Документ описывает **текущее** устройство системы.

---

## 1. Компоненты

```
Браузер
  │  React 19 (Vite, TS)
  │  Дашборд: сводка, список репозиториев, «не отслеживаются», «зеркала»
  ▼
FastAPI (backend)
  ├─ /api/v1/scan            — запуск/статус сканирования
  ├─ /api/v1/repositories    — CRUD, track/untrack, status, compare, recommendations, mirror, mirror-policy
  ├─ /api/v1/mirror          — candidates, poll
  ├─ /api/v1/webhooks        — GitHub / GitFlic (HMAC)
  ├─ /api/v1/dashboard       — агрегированная сводка
  └─ /api/v1/health
  │
  ├─ Discovery Service          — рекурсивный поиск .git/, исключения, глубина
  ├─ Git Abstraction Layer      — pygit2 (status, log, compare) + shell git (fetch, rev-list)
  ├─ Status Service             — локальная модель (current/behind/ahead/diverged/dirty/...)
  ├─ Remote Comparator          — fetch + rev-list (в пределах провайдера)
  ├─ Mirror Service (R8)        — GitHub ↔ GitFlic: API-клиенты, сравнение HEAD SHA
  ├─ Mirror Scheduler (R9)      — polling раз в N минут + webhook-инвалидация
  ├─ Recommendation Service     — команды по состоянию (local + mirror)
  └─ SQLite (или PostgreSQL)    — repositories, repository_status, repository_mirror_status, scan_runs, webhook_events
```

---

## 2. Backend: слои

```
app/api/v1/*            HTTP-слой: валидация схем, коды ответов
app/services/*          бизнес-логика:
                          discovery_service
                          status_service
                          remote_service
                          mirror_service          ← NEW (R8)
                          mirror_scheduler        ← NEW (R9)
                          recommendation_service
app/providers/*         клиенты внешних API:       ← NEW
                          github_client (REST v3)
                          gitflic_client (REST)
                          base (rate-limit, retry, backoff)
app/git/*               pygit2_backend, command_backend
app/db/repositories     Repository-паттерн
app/models/*            ORM (SQLAlchemy 2.0)
app/schemas/*           Pydantic v2
app/errors.py           доменные исключения
```

**Правила слоёв:**
- Сервисы не используют `HTTPException` — только доменные ошибки.
- Git-операции не выполняются в HTTP-слое.
- Внешние API — **только** через `app/providers/*` (единая обработка rate-limit, retry, токенов).
- Read-only операции не вызывают мутирующих Git-команд.

---

## 3. Discovery: как находим репозитории

```
SCAN_ROOTS=/home/user/projects,/home/user/work
SCAN_DEPTH=3
SCAN_IGNORE=node_modules,.venv,vendor,dist,build,target
```

1. Рекурсивный обход `SCAN_ROOTS` до `SCAN_DEPTH`.
2. Признак репозитория — `.git/` (директория или файл `gitdir:` для worktree).
3. Для каждого пути: обновить `last_seen_at` или создать с `tracked=false`.
4. Пропускать пути, содержащие `SCAN_IGNORE`.
5. **Не заходить в `.git/`** (кроме корня репозитория).

**Почему pygit2:** `Repository.status()` работает через libgit2 in-process, без spawn. При 20+ репозиториях subprocess-подход даёт ~11 мс/вызов, pygit2 — ~2 мс; главное — нет накладных расходов на spawn.

---

## 4. Локальная модель состояния (Status Service)

Кортеж `(state, ahead, behind, dirty)`:

1. Открыть репозиторий через pygit2.
2. `HEAD` detached → `state=detached`.
3. `repo.status()` → `modified / staged / untracked / conflicted`.
4. Нет upstream → `state=no_upstream`.
5. `git rev-list --left-right --count HEAD...@{u}` → `ahead/behind` **после fetch**.
6. Классификация по приоритету: `dirty` > `diverged` > `ahead` > `behind` > `current`.

**Важно:** `dirty` и `ahead/behind` ортогональны. В `state` — «наиболее требующее внимания», но в ответе API отдаются все поля.

---

## 5. Remote Comparator: сравнение в пределах провайдера

**Fetch** (`git fetch --all --prune`, таймаут 30 с) — обязателен; ошибка → `remote_status=unavailable`; **не изменяет** рабочую директорию и локальные ветки.

**Compare** — два пути:
1. **Локальный** (v0.1.0): `git rev-list --left-right --count HEAD...@{u}` и pygit2.
2. **Провайдерский** (v0.2.0, опционально): Compare API GitHub (для обогащения — авторы, сообщения); в v0.1.0 не используется.

---

## 6. Read-only политика и мутации

**v0.1.0 — только чтение.** `pull`, `push`, `merge`, `stash` не выполняются. Рекомендации формируются, но не запускаются. Это осознанный trade-off (ADR-0003). В v0.2.0 добавлены **явные** мутации `POST /repositories/{id}/actions/{action}` с `confirm=true` и аудитом (`action_log`); destructive-команд по-прежнему нет.

---

## 7. Mirror Comparator: GitHub ↔ GitFlic (R8/R9)

**Задача.** Обнаружить, что один и тот же проект по-разному представлен в двух провайдерах: отсутствует в одном, отстаёт, разошёлся или был force-push'нут в один из них (переписанная история). Локальный клон не решает задачу: он может знать только один remote.

**Реализация v0.2.0 (Sprint 9):** `app/providers/{github,gitflic}_client.py`, `MirrorService`, `MirrorScheduler`, webhooks. При разных SHA классификация использует даты коммитов, полученные из API (`sha+date-heuristic`); history/compare API провайдеров — следующий шаг.

### 7.1. Поток сравнения

```
Пользователь / Polling / Webhook
  → MirrorService.refresh(repository)
      ├─ GitHubClient.get_branch(repo.github_full_name, branch)   → {sha, date, private}
      ├─ GitFlicClient.get_branch(repo.gitflic_full_name, branch) → {sha, date, private}
      └─ classify(github_sha, gitflic_sha, canonical, mirror_expected)
  → MirrorStatus
  → upsert repository_mirror_status
  → RecommendationService.enrich
```

**`classify` — детерминированная функция** (без API): сравнивает SHA и, при необходимости, даты последних коммитов и родительские связи. Если SHA разные — вызывается `GitHubClient.compare`/`GitFlicClient.compare` **внутри одной платформы**, чтобы понять, является ли один SHA предком другого (тогда это `behind_*`), или истории разошлись (`diverged` / `history_rewritten`).

### 7.2. Классификация `mirror_status`

| Ситуация | Определение |
|---|---|
| `in_sync` | `github_sha == gitflic_sha` |
| `missing_on_gitflic` | `gitflic_full_name` пуст / API вернул 404 |
| `missing_on_github` | `github_full_name` пуст / API вернул 404 |
| `behind_gitflic` | `canonical=github`, `gitflic_sha` — предок `github_sha` (проверено compare внутри GitFlic) |
| `behind_github` | `canonical=gitflic`, симметрично |
| `diverged` | SHA разные, ни один не предок другого, **но** даты/родители указывают на общую базу |
| `history_rewritten` | SHA разные, общей базы в истории не найдено (или количество общих предков резко упало) |
| `not_applicable` | `mirror_expected=false` |
| `unavailable` | Один из API недоступен / rate-limit / токен не задан |

`history_rewritten` — **критический** алерт, а не warning: это признак force-push'а или сброса истории, который зеркало не переживёт без ручного вмешательства.

### 7.3. Polling + webhook

**Polling.** `MirrorScheduler` — одна asyncio-задача в `lifespan`, интервал `MIRROR_POLL_INTERVAL_SECONDS` (default 300). На каждом тике:

1. Взять `tracked=true ∧ mirror_expected=true`, у которых `checked_at` старше TTL.
2. **Параллельно** (но с ограничением concurrency) обновить `MirrorStatus`.
3. При `rate_remaining < 10%` у провайдера — удвоить интервал до восстановления.
4. Остановка приложения даёт доиграть текущий тик (graceful stop).

**Webhook.** `POST /webhooks/gitflic` и `POST /webhooks/github`:

1. Валидация HMAC (`X-Hub-Signature-256` для GitHub, аналогично для GitFlic) при заданном `WEBHOOK_SECRET`.
2. Записать `webhook_events` (payload, `received_at`, `status=pending`).
3. Найти `repository` по `full_name`; поставить `refresh` в очередь.
4. Ответ `202 Accepted` **до** обработки (webhook не должен ждать API).

Webhook **не заменяет** polling: если webhook не настроен/пропущен (сеть, downtime), polling догонит. Polling **не заменяет** webhook: без него лаг до 5 минут.

### 7.4. Rate limits и кэш

- `GITHUB_TOKEN` (scope `repo` для приватных) — 5000 req/час. `GITFLIC_TOKEN` — по докам провайдера.
- Кэш `MIRROR_STATUS_TTL_SECONDS` (300) — дашборд не делает 2×N запросов на каждый рендер.
- `POST /mirror/refresh` обходит кэш — для ручной проверки.
- При 403/429 — `unavailable` + warning в лог; polling замедляется автоматически (см. §7.3).

### 7.5. Провайдеры и приватность

Большинство проектов **приватные**. Это значит:

- Для GitHub — токен с `repo` scope обязателен, иначе `missing_on_*` будет ложно-положительным.
- Для GitFlic — токен с доступом к приватным проектам.
- Публичные проекты работают без токена, но с rate-limit (60/час GitHub). В этом случае `unavailable` при исчерпании.

**Никогда** не логируем содержимое файлов и diff'ы — только метаданные (SHA, даты, private флаг).

### 7.6. Обнаружение кандидатов

`GET /mirror/candidates`:

1. `GitHubClient.list_repos()` → `{full_name, private, default_branch}` (пагинация).
2. `GitFlicClient.list_projects()` → аналогично.
3. Дедупликация по нормализованному `name` (без учёта `owner/`).
4. Классификация: `github_only / gitflic_only / both / unknown`.
5. Для каждого — `suggested_action`: «создать зеркало в GitFlic», «пометить как осознанно односторонний», «сверить истории».

Автоматических мутаций нет: пользователь решает, что делать с кандидатом.

---

## 8. Данные

| Таблица | Назначение |
|---------|------------|
| `repositories` | путь, alias, tracked, remote_url, provider, **mirror-политика** |
| `repository_status` | последний снимок локального статуса |
| **`repository_mirror_status`** | **последний снимок межпровайдерного состояния (R8) — v0.2.0** |
| `scan_runs` | история сканирований |
| **`webhook_events`** | **события от GitHub/GitFlic (R9) — v0.2.0** |

Кэш локального статуса: `STATUS_TTL_SECONDS=60`. Кэш mirror-статуса: `MIRROR_STATUS_TTL_SECONDS=300`.

---

## 9. Frontend

- **Дашборд** — карточки репозиториев. Две цветовые полосы: **локальный статус** и **mirror-статус**. Фильтры: «Все», «Локально требуют внимания», «Зеркала расходятся», «Не отслеживаются».
- **Секция «Зеркала»** — `mirror_status != in_sync ∧ mirror_expected`. Для каждого — `suggested_action` и готовая команда (только копирование).
- **Детали репозитория** — две панели: локальная (ветка, upstream, ahead/behind, файлы, коммиты) и зеркальная (GitHub SHA/дата, GitFlic SHA/дата, `mirror_status`, политика).
- **Настройка политики** — `canonical_provider`, `mirror_expected`, `mirror_policy` в модалке деталей.
- **Кнопка «Обновить»** — обновляет **оба** статуса (локальный + mirror).

### 9.1. Состояние UI и Saved Views (v0.4.0)

```
stores/
  useTableStore     — сортировка, фильтры, выбранные строки, видимость/порядок/ширина колонок
  useViewsStore     — именованные представления {filters, sort, columns, widths}
  useCommandStore   — открытие палитры, недавние команды
```

- Zustand + middleware `persist` (`localStorage`) с версионированием (`version: 1`)
  и миграциями. Ключи: `table.state.v1`, `views.v1`, `theme` (уже существует).
- Источник истины на клиенте — store, компоненты только читают селекторы.
  Это исключает рассинхрон между чипами, таблицей и URL.
- v0.5.0: опциональная синхронизация `views` в БД (`saved_views`) через API;
  локальный store остаётся кэшем и работает offline.
- Query string — проекция store (`?state=dirty&mirror=behind_gitflic&view=...`),
  при загрузке — гидратация store.

### 9.2. Command Palette (v0.4.0)

```
<CommandPalette/>
  ├─ commandRegistry: [{id, title, keywords, run(), when?}]
  ├─ providers: repositories (dashboard cache), actions (fetch/push/migrate),
  │             navigation (dashboard/settings/repo)
  ├─ fuzzy match (client-side, без сетевых вызовов)
  └─ useHotkeys('mod+k', '?', '/', ...)
```

- Палитра не знает о роутере напрямую: команды вызывают `navigate()`/API через
  переданные callbacks, поэтому компонент тестируется изолированно.
- Глобальный обработчик клавиш игнорирует события из `input/textarea/select`
  и `contentEditable`.
- Мутирующие команды из палитры открывают ту же модалку подтверждения, что и
  кнопки в UI (единый `ActionConfirmDialog`).

### 9.3. Производительность

- Таблица: мемоизированные селекторы, сортировка/фильтрация в store, виртуализация —
  при > 500 строк (v0.4.1).
- Тяжёлые виджеты (recharts, heatmap) — `React.lazy`; бюджет entry bundle — 100 kB gzip.
- Экспорт CSV/JSON — на клиенте из текущего среза, без новых серверных отчётов.

### 9.4. A11y и stale-состояние

- Бейджи: цвет + иконка/форма; `aria-label` описывает состояние.
- Модалки: `role="dialog"`, `aria-modal`, focus trap, возврат фокуса.
- Stale: вычисляется из `checked_at` и `remote_status`; данные не скрываются,
  блок получает opacity и бейдж «Устарело».

---

## 10. Docker

- `docker-compose.yml` — backend + frontend; SQLite-volume.
- Bind на `127.0.0.1` (local-only); наружу не публикуется.
- Webhook-эндпоинты: для локального приёма webhook от GitHub/GitFlic нужен публичный URL. Варианты: (а) reverse-proxy с basic-auth + allowlist IP провайдера, (б) `ngrok`/`cloudflared` для dev, (в) только polling (webhook опционален). Решение фиксируется в ADR-0006 (TODO).

---

## 11. Что ещё не сделано (v0.4+)

- Advanced Data Table: batch selection, управление колонками, контекстное меню (S18).
- Filter chips, Saved Views, URL-состояние (S19).
- Command Palette и клавиатурная навигация (S20).
- A11y-иконки, stale-индикатор, Conflict Manager, Telegram-уведомления, heatmap, export (S21).
- Синхронизация saved views в БД (v0.5.0).
- История статусов (trend: как часто репозиторий был `dirty`; как часто `behind_gitflic`).
- Полноценный GitFlic Compare API (сейчас — compare внутри GitFlic, классификация по SHA/датам).