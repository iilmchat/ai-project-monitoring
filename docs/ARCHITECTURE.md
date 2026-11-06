# ARCHITECTURE — как устроен IIRuchating

Документ описывает **текущее** устройство системы. Раздел §10 (Docker)
реализован в Sprint 24; §11 (Python/Node dependencies) — в Sprint 25–26.
Разделы §12–14 — **план v0.6.0** (Sprint 28–30); они фиксируют проектное
решение до реализации.

---

## 1. Компоненты

```
Браузер
  │  React 19 (Vite, TS)
  │  Дашборд: сводка, список репозиториев, «не отслеживаются», «зеркала»
  ▼
FastAPI (backend)
  ├─ /api/v1/scan            — запуск/статус сканирования
  ├─ /api/v1/repositories    — CRUD, track/untrack, status, compare, recommendations,
  │                            mirror, mirror-policy, docker, dependencies
  │                            security (v0.6.0), insights (v0.6.0)
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
  ├─ Docker Service (v0.5.0)    — read-only docker SDK (UDS/npipe), container status
  ├─ Dependency Service         — requirements.txt / package.json → PyPI / npm
  ├─ Security Service (v0.6.0)  — OSV.dev CVE + regex secret scan (read-only)
  ├─ Insights Service (v0.6.0)  — git log: hotspots, commit frequency (DORA-lite)
  └─ SQLite (или PostgreSQL)    — repositories, repository_status, repository_mirror_status,
                                  scan_runs, webhook_events, dependency_cache,
                                  security_cache
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
                          docker_service          ← NEW (v0.5.0; docker SDK + matcher)
                          dependency_service      ← NEW (v0.5.0)
                          security_service        ← NEW (v0.6.0)
                          insights_service        ← NEW (v0.6.0)
app/providers/*         клиенты внешних API:
                          github_client (REST v3)
                          gitflic_client (REST)
                          pypi_client             ← NEW (v0.5.0)
                          npm_client              ← NEW (v0.5.0)
                          osv_client              ← NEW (v0.6.0)
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
- Docker — только через `DockerService`; никаких прямых вызовов демона из роутеров.
- Манифесты зависимостей читает `DependencyService`; `pip`/`npm`/`pnpm` не запускаются.
- `SecurityService` работает только с OSV.dev и файлами рабочей директории;
  полные значения секретов не покидают сервис.
- Git-историю для `InsightsService` читает только `git log`/`git rev-list`
  через контролируемый subprocess; `fetch`/`checkout` не вызываются.
- Read-only операции не вызывают мутирующих Git-команд, lifecycle-операций Docker
  и установки пакетов.

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
| **`dependency_cache`** | **TTL-кэш latest-версий PyPI/npm (24 ч) — v0.5.0** |
| **`security_cache`** | **TTL-кэш ответов OSV.dev по `package@version` (6 ч) — v0.6.0** |

Кэш локального статуса: `STATUS_TTL_SECONDS=60`. Кэш mirror-статуса: `MIRROR_STATUS_TTL_SECONDS=300`.
Кэш Docker: `DOCKER_STATUS_TTL_SECONDS=30`. Кэш зависимостей: `DEPENDENCY_CACHE_TTL_SECONDS=86400`.
Кэш security (OSV): `SECURITY_CACHE_TTL_SECONDS=21600`; secret-scan — in-memory 300 с.
Кэш insights: in-memory `INSIGHTS_CACHE_TTL_SECONDS=300`.

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
- Docker- и dependency-блоки (v0.5.0) — lazy, загружаются при раскрытии карточки/
  деталей; dashboard не делает N запросов к Docker/PyPI/npm при первом рендере.

### 9.4. A11y и stale-состояние

- Бейджи: цвет + иконка/форма; `aria-label` описывает состояние.
- Модалки: `role="dialog"`, `aria-modal`, focus trap, возврат фокуса.
- Stale: вычисляется из `checked_at` и `remote_status`; данные не скрываются,
  блок получает opacity и бейдж «Устарело».

### 9.5. Тёмные графики (v0.5.0)

```
index.css
  :root  — светлые M3-токены
  .dark  — тёмные M3-токены
  --chart-grid, --chart-axis, --chart-legend,
  --chart-tooltip-bg, --chart-tooltip-border, --chart-tooltip-text,
  --chart-series-1..8

tailwind.config.js
  colors.chart.* → var(--chart-*)

DashboardCharts.tsx
  XAxis / YAxis / CartesianGrid / Legend / Tooltip / Cell → chart-токены
```

- recharts принимает `var(--chart-*)` в SVG-атрибутах (`stroke`, `fill`), поэтому
  переключение темы не требует пересоздания графиков.
- Семантика серий сохраняется: `current` — emerald, `dirty` — amber, `ahead` —
  violet, `behind` — orange, `diverged`/`error` — red, нейтральные — outline.
- Тултип — surface-container/on-surface, сетка — outline-variant с opacity;
  контраст текста ≥ 4.5:1, линий ≥ 3:1.
- Пустые данные — текстовое состояние; компонент не рендерит пустой SVG.

### 9.6. Docker и зависимости (v0.5.0)

- **Docker:** блок в деталях/карточке показывает `state`, `health`, image,
  compose service и опубликованные порты. `status=unavailable` — отдельное
  состояние с причиной (`Docker daemon not running`, `permission denied`,
  `disabled`) и ссылкой на KI-009; карточка репозитория остаётся работоспособной.
- **Зависимости:** блок группирует Python/Node, показывает счётчики и список
  `declared → latest` с severity. Ошибка одного ecosystem не скрывает другой.
- Оба блока загружаются лениво и не участвуют в первичном запросе `/dashboard`.
- Управляющих действий нет: только просмотр и `?refresh=true`.

### 9.7. Security и Insights (v0.6.0, план)

```
<SecurityPanel repoId>
  ├─ useSecurity(repoId)   → GET /repositories/{id}/security
  ├─ severity badges (critical/high/medium/low/unknown)
  ├─ vulnerability list: package@version → fixed, CVE/GHSA links
  └─ secrets: file:line + type + masked preview (full value never in DOM)
```

```
<InsightsPanel repoId>
  ├─ useInsights(repoId, days) → GET /repositories/{id}/insights
  ├─ HotspotsList  — top-5 paths + relative bar
  └─ CommitSparkline — daily/weekly buckets
```

- Оба блока — `React.lazy`, монтируются при раскрытии карточки/деталей; dashboard
  не делает N запросов на первый рендер.
- `version_source=lower_bound` и `unknown_packages` визуально отличаются от
  проверенных «чистых» пакетов.
- Секреты: сервер уже отдаёт только masked `preview`; клиент не пытается
  восстановить значение и не пишет его в `localStorage`/логи.
- Состояния `unavailable`, `partial`, `no_manifest`, `shallow_clone`, `timeout`
  рендерятся как пояснение, а не как пустой график или 500.
- Severity передаётся не только цветом: текстовая подпись + иконка; контраст AA
  в light/dark.

### 9.8. Collaboration export (v0.6.0, план)

- **Markdown:** `buildDashboardMarkdown(summary, repositories, filters)` —
  чистая функция, тестируется без DOM; экранирует `|`, не генерирует HTML;
  копирование через `navigator.clipboard` с fallback и toast.
- **Workspace JSON:** `exportWorkspace()` собирает `views` + `table` из Zustand
  store; `importWorkspace(file)` валидирует `version`/схему/размер (≤ 1 MiB) и
  применяет `replace`/`merge`; при ошибке store не меняется.
- Экспорт не читает API и не содержит токенов/секретов; серверные эндпоинты не
  добавляются.
- После импорта — реактивное обновление store, без перезагрузки страницы.

---

## 10. Docker

### 10.1. Текущая конфигурация

- `docker-compose.yml` — backend + frontend; SQLite-volume.
- Bind на `127.0.0.1` (local-only); наружу не публикуется.
- Backend-образ: Python 3.12 + libgit2 + git; Docker CLI в образ не ставится.
- Webhook-эндпоинты: для локального приёма webhook от GitHub/GitFlic нужен публичный URL. Варианты: (а) reverse-proxy с basic-auth + allowlist IP провайдера, (б) `ngrok`/`cloudflared` для dev, (в) только polling (webhook опционален). Решение фиксируется в ADR-0006 (TODO).

### 10.2. Docker-интеграция v0.5.0 (Sprint 24)

**Цель.** Показать в карточке репозитория, запущен ли его контейнер, на каком
порту и в каком состоянии — без управления контейнерами.

```
Браузер → FastAPI /repositories/{id}/docker
              → DockerService.get_container_status(repo_path)
                  → asyncio.to_thread(...)
                      → docker SDK (DockerClient.from_env / base_url)
                          → Docker Engine API over UDS / npipe
                  → matcher: bind mounts + compose labels + DOCKER_PATH_MAP
                  → normalize → DockerStatus
```

**Монтирование сокета (Docker Compose):**

```yaml
services:
  backend:
    volumes:
      - ./data:/app/data
      - C:/Projects:/projects
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      DOCKER_ENABLED: "true"
      DOCKER_HOST: unix:///var/run/docker.sock
      DOCKER_PATH_MAP: ${DOCKER_PATH_MAP:-C:/Projects=/projects}
      DOCKER_STATUS_TTL_SECONDS: "30"
      DOCKER_TIMEOUT_SECONDS: "3"
```

Для Docker Desktop с Linux-контейнерами путь внутри контейнера — тот же
`/var/run/docker.sock`. На Windows при локальном `uvicorn` `DOCKER_HOST` можно
не задавать: Docker SDK выберет named pipe `\\.\pipe\docker_engine`.
Если ни UDS, ни npipe недоступны, сервис возвращает `status=unavailable`, а не
падает.

**Path mapping.** Backend видит проекты как `/projects/<repo>`, а label
`com.docker.compose.project.working_dir` и bind-mount `Source` содержат
host-путь (`C:/Projects/<repo>`). `DOCKER_PATH_MAP` переводит host-префикс в
container-префикс перед сравнением с `repository.path`; суффикс сохраняет
регистр, потому что Linux-пути регистрозависимы. Без маппинга path-сравнение
пропускается, и matcher использует `compose_project`/имя контейнера
(`match` показывает правило).

**Поток:**

1. Проверить `DOCKER_ENABLED` и кэш (`DOCKER_STATUS_TTL_SECONDS=30`).
2. В worker-thread: `docker.from_env(timeout=...)` или
   `DockerClient(base_url=DOCKER_HOST)`.
3. `client.ping()`, затем `client.containers.list(all=True)`.
4. Сопоставить с `repository.path`: bind `Source`/`Destination`, compose
   `working_dir`, compose project, имя контейнера/образа.
5. Нормализовать `state`, `health`, порты, compose metadata.
6. Закрыть клиент, обновить кэш, вернуть `DockerStatus`.

**Маппинг статуса:**

| Найдено | `status` |
|---------|----------|
| нет совпадений | `not_found` |
| есть `running`/`restarting` | `running` |
| есть, но все остальные | `stopped` |
| disabled / `DockerException` / connection error | `unavailable` |

**Почему Docker SDK.** Выбран `docker==7.1.0` (ADR-0007): он даёт `Mounts`,
`Labels`, `Ports`, `DockerException` и сам поддерживает UDS/npipe. Синхронные
вызовы выполняются в `asyncio.to_thread`. Docker CLI в образ не ставится;
SDK устанавливается из `requirements.txt`. Тесты используют fake-клиент, поэтому
реальный демон для `pytest` не нужен.

**Конфигурация:**

| Переменная | Назначение |
|------------|------------|
| `DOCKER_ENABLED` | `false` — не обращаться к Docker (`status=unavailable`) |
| `DOCKER_HOST` | Явный endpoint; пусто — SDK default (UDS/npipe) |
| `DOCKER_PATH_MAP` | `host=container[,host2=container2]` |
| `DOCKER_STATUS_TTL_SECONDS` | TTL кэша (default 30) |
| `DOCKER_TIMEOUT_SECONDS` | Таймаут SDK (default 3) |

**Безопасность:**

- Docker socket = root-эквивалент на хосте. `:ro` на bind-mount **не**
  ограничивает Docker API: через сокет всё равно можно запускать контейнеры.
- Приложение использует только `ping()` и `containers.list(all=True)`;
  lifecycle-операции запрещены на уровне кода и grep-аудита.
- Сокет не проксируется наружу; API остаётся local-only.
- `DOCKER_ENABLED=false` — аварийный выключатель.
- В ответ не попадает сырой JSON Docker: только нормализованные поля.

**Windows-ограничения:** см. KI-009. Docker Desktop должен быть запущен;
доступ к named pipe может требовать прав администратора/членства в `docker-users`.
При `permission denied` UI показывает причину, а не 500.

---

## 11. Dependency Management (v0.5.0, Sprint 25–26)

**Задача.** Показать, какие объявленные зависимости устарели, не изменяя
репозиторий и не запуская пакетные менеджеры.

**Статус:** Python (`requirements.txt`, PyPI, кэш) реализован в Sprint 25;
Node (`package.json`, npm) — в Sprint 26. `ecosystem=all` объединяет отчёты.

### 11.1. Поток

```
GET /repositories/{id}/dependencies
  → DependencyService
      ├─ manifest detection: requirements.txt, package.json
      ├─ parser → [{name, declared, kind, line, section}]
      ├─ cache lookup (dependency_cache, 24 ч)
      ├─ registry fetch (PyPI / npm) для miss/stale, concurrency 4
      └─ normalize → DependencyReport
```

### 11.2. Парсинг

| Файл | Что читаем | Игнорируем |
|------|------------|------------|
| `requirements.txt` | `==`, `~=`, `>=`, `>`, `<=`, `<`; extras; markers; `-r` include (глубина ≤ 3) | `-e`, VCS, local paths, URL, hashes (для сравнения) |
| `package.json` | `dependencies`, `devDependencies`; `^`, `~`, exact | `workspace:`, `file:`, `link:`, `git+`, `http(s):`, `npm:` aliases |

- Include-файлы `requirements.txt` разрешены только внутри корня репозитория;
  циклы, path traversal и выход за корень пропускаются. `-c`/constraints и
  `--index-url`/`--hash` не являются объявлениями зависимостей.
- Lock-файлы и транзитивные зависимости не анализируются.
- `current` — exact-версия или нижняя граница диапазона; для сложных диапазонов
  `current=null`, `status=unknown`. Без `packaging`/`semver`-библиотек:
  сравнение release-части версии (`major.minor.patch`) собственное.
- `declared` сохраняет исходную строку (без inline-комментария); extras и
  environment markers не участвуют в запросе к PyPI.

### 11.3. Кэш

- Таблица `dependency_cache(key*, ecosystem, package, latest_version, etag,
  payload, checked_at)`.
- Ключ `pypi:<normalized-name>` / `npm:<normalized-name>`.
- TTL `DEPENDENCY_CACHE_TTL_SECONDS=86400` (24 ч); кэш переживает перезапуск.
- `DependencyService` использует `session_factory`: чтение/запись кэша идут в
  отдельных коротких сессиях, поэтому пакеты можно проверять конкурентно.
- Single-flight на ключ (asyncio lock): N одновременных запросов одного пакета
  не делают N сетевых вызовов; после lock-а кэш перечитывается.
- Stale-while-revalidate: при ошибке реестра и наличии stale-записи отдаётся
  `source=stale_cache` с прежним `latest`; `checked_at` отчёта — момент
  формирования ответа.
- `refresh=true` обходит TTL для запрошенного репозитория, но обновляет кэш.

### 11.4. Registry clients

- PyPI: `GET https://pypi.org/pypi/{name}/json`, latest = `info.version`;
  имя URL-encode.
- npm: `GET https://registry.npmjs.org/{name}/latest`; scoped-имя кодируется
  (`@scope%2Fname`), latest = `version`.
- Timeout `DEPENDENCY_HTTP_TIMEOUT=5`; User-Agent `IIRuchating/0.5`.
- 429/5xx — backoff 0.5/1/2 с, максимум 3 попытки; 404 — `not_found`
  (пакет получает `status=unknown`).
- Concurrency ≤ `DEPENDENCY_CHECK_CONCURRENCY=4`; исключения клиента
  превращаются в `registry_unavailable`, а не в 500.
- В логи не пишутся тела манифестов; ответы реестров не кэшируются целиком,
  только latest/etag/payload статуса.

### 11.5. Partial failure

- Ошибка одного пакета не скрывает остальные: пакет получает `unknown`/`latest=null`.
- Если реестр недоступен и кэша нет — `ecosystem.status=unavailable`,
  `error` (`rate_limited`, `registry_unavailable`, `timeout`), HTTP 200.
- Один ecosystem не влияет на другой: Python может быть `ok`, Node — `unavailable`.
- `source` и `error` позволяют UI показать stale/частичное состояние.

### 11.6. Read-only и безопасность

- Читаются только фиксированные имена в корне репозитория (+ относительные
  include для `requirements.txt`); произвольные пути запрещены.
- `pip`/`npm`/`pnpm` не запускаются; shell не используется.
- Имена пакетов URL-encode; URL из манифеста не используются как адрес запроса.
- Приватные registry и токены — вне scope v0.5.0.
- Запись — только в `dependency_cache`; рабочая директория репозитория не меняется.

---

## 12. Security (v0.6.0, Sprint 28 — план)

**Задача.** Показать уязвимости в объявленных зависимостях и потенциальные
секреты в рабочей директории, не устанавливая пакеты и не изменяя репозиторий.

### 12.1. Поток

```
GET /repositories/{id}/security
  → SecurityService
      ├─ manifest parsing (переиспользует DependencyService v0.5.0)
      ├─ version resolution → [{package, version, version_source}]
      ├─ security_cache lookup (6 ч)
      ├─ OsvClient.query_batch(...) для miss/stale
      ├─ severity mapping + дедупликация по osv_id
      ├─ SecretScanner.scan(repo.path)   (если include_secrets)
      └─ normalize → SecurityReport
```

### 12.2. Версии и честность результата

- `exact` — `==` в `requirements.txt` или точная версия в `package.json`.
- `lower_bound` — нижняя граница диапазона (`>=`, `>`, `~=`, `^`, `~`).
  OSV проверяет **эту** версию; в ответе `version_source=lower_bound`, UI
  показывает пометку «диапазон».
- Если версия не извлекается (`*`, `latest`, сложный диапазон, `ignored`-пакет),
  пакет попадает в `unknown_packages` и **не** считается проверенным.
  Это важнее, чем «красивый» нулевой отчёт: отсутствие данных не равно
  отсутствию уязвимостей.
- Транзитивные зависимости и lock-файлы не проверяются (как в v0.5.0).

### 12.3. OSV.dev

- Клиент `app/providers/osv_client.py`: `POST /v1/querybatch` с массивом
  `queries: [{package: {name, ecosystem}, version}]`; fallback — поштучный
  `POST /v1/query`.
- Ecosystem: `PyPI` / `npm`.
- Timeout 10 с, concurrency ≤ 4, backoff 0.5/1/2 с на 429/5xx (max 3 попытки).
- Ответ нормализуется в `{osv_id, aliases, summary, severity, cvss, fixed}`
  сразу на границе провайдера; сервис не работает с сырым JSON OSV.
- 404/пустой результат по пакету — «уязвимостей нет», а не ошибка.
- Ошибка batch-запроса деградирует до поштучных запросов; полная недоступность
  OSV → `ecosystem.status=unavailable`.

### 12.4. Severity

| CVSS v3 | severity |
|---------|----------|
| ≥ 9.0 | `critical` |
| 7.0–8.9 | `high` |
| 4.0–6.9 | `medium` |
| < 4.0 | `low` |
| нет CVSS | severity из advisory, иначе `unknown` |

CVSS берётся из `severity[].score` (vector → base score). Если у advisory
несколько оценок, используется максимальная. `fixed_version` — минимальная
`fixed`-версия среди `affected.ranges`; если её нет — `null` (исправления не
известно).

### 12.5. Кэш и деградация

- `security_cache(key*, ecosystem, package, version, payload, checked_at)`,
  ключ `osv:<ecosystem>:<package>:<version>`, TTL 6 ч.
- Кэш переживает перезапуск; `refresh=true` обходит TTL только для запрошенного
  репозитория.
- Stale-while-revalidate: при 429/5xx/timeout отдаётся последний payload, отчёт
  остаётся HTTP 200; `checked_at` показывает актуальность.
- Пустой результат тоже кэшируется (negative cache), иначе «чистые» пакеты
  будут дёргать OSV при каждом открытии.
- Один ecosystem не влияет на другой; секреты считаются независимо.

### 12.6. Secret Scanner

**Источник файлов.** `git ls-files -z -co --exclude-standard` — tracked +
untracked non-ignored. Это даёт «рабочую директорию» и уважает `.gitignore`,
не обходя `node_modules`/`.venv`. История Git не читается.

**Пайплайн:**

1. Получить список путей (read-only команда, без `--cached`-мутаций).
2. Отфильтровать каталоги/расширения, бинарные файлы (NUL-байт в первых 8 KiB),
   размер > 1 MiB; остановиться на `SECRET_SCAN_MAX_FILES`.
3. Прочитать файл как UTF-8 с `errors="replace"`, построчно применить regex.
4. Совпадение → `{file, line, type, severity, confidence, preview}`; `preview`
   строится маскированием (оставить префикс 4 символа и суффикс 4, остальное
   `****`), полное значение сразу отбрасывается.
5. Строка с `# iiruchating:ignore-secret` пропускается (подавление FP).
6. Результат — in-memory кэш 300 с; в БД и логи не пишется.

**Правила:**

| type | regex (сокращённо) | severity |
|------|-------------------|----------|
| `aws_access_key` | `AKIA[0-9A-Z]{16}` | high |
| `aws_secret_key` | assignment 40-char base64 рядом с `aws_secret` | high |
| `github_token` | `gh[pousr]_[A-Za-z0-9]{36,}` | high |
| `jwt` | `eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.` | medium |
| `private_key` | `-----BEGIN (RSA\|OPENSSH\|EC\|PGP) PRIVATE KEY-----` | high |

Regex-набор фиксирован; эвристики по entropy и пользовательские правила — вне
scope v0.6.0 (высокий FP-rate). Ограничения — KI-012.

### 12.7. Read-only и безопасность

- Файлы только читаются; рабочая директория, индекс и `.git` не меняются.
- `pip`/`npm`/`pnpm` не запускаются; shell для секретов не используется.
- Полные секреты не попадают в ответ, логи, метрики, `action_log` и ошибки.
- API local-only; результаты security не экспортируются в workspace JSON.
- Сканирование ограничено по числу файлов и размеру — защита от DoS на
  огромных деревьях.

Решение о выборе OSV.dev и regex-подхода (вместо локальной базы advisories и
gitleaks) фиксируется в ADR-0009 (Sprint 28).

### 12.8. Конфигурация

| Переменная | Назначение |
|------------|------------|
| `OSV_API_URL` | Base URL OSV.dev (default `https://api.osv.dev`) |
| `SECURITY_CACHE_TTL_SECONDS` | TTL CVE-кэша (default 21600) |
| `SECURITY_CHECK_CONCURRENCY` | Параллельные запросы (default 4) |
| `SECURITY_HTTP_TIMEOUT` | Timeout OSV (default 10 с) |
| `SECRET_SCAN_ENABLED` | Глобальный выключатель (default true) |
| `SECRET_SCAN_MAX_FILES` | Лимит файлов (default 5000) |
| `SECRET_SCAN_MAX_FILE_BYTES` | Лимит размера файла (default 1 MiB) |
| `SECRET_SCAN_TTL_SECONDS` | TTL in-memory кэша (default 300) |

---

## 13. Insights (v0.6.0, Sprint 29 — план)

**Задача.** Показать, какие файлы чаще всего меняются (кандидаты на
рефакторинг) и как часто ветка получает коммиты (DORA-lite proxy).

### 13.1. Почему subprocess, а не pygit2

Для churn нужен список файлов **на каждый коммит** за окно. `pygit2`-revwalk +
diff на большом репозитории дороже и требует ручного обхода деревьев; `git log
--name-only` уже отдаёт готовый список и корректно работает с pack-файлами.
Поэтому используется `git` CLI, но **строго** через контролируемый runner:

- `asyncio.create_subprocess_exec("git", "-C", repo.path, "log", ...)`;
- `env` с `GIT_OPTIONAL_LOCKS=0`, без интерактива и pager (`--no-pager`);
- timeout 10 с, kill процесса, лимит stdout 8 MiB;
- stderr не пробрасывается в ответ (только в structlog без путей/содержимого).

Event loop не блокируется: ожидание процесса асинхронное. Для коротких вызовов
допустим `asyncio.to_thread`, но subprocess-вариант предпочтителен.

### 13.2. Поток

```
GET /repositories/{id}/insights?days=30
  → InsightsService
      ├─ resolve_branch(): upstream → main → master → HEAD
      ├─ cache lookup (repo_id, branch, days; 300 с)
      ├─ hotspots:
      │    git log --since="<days> days ago" --no-merges --name-only --pretty=format:
      ├─ sparkline:
      │    git log --since="<days> days ago" --format=%ad --date=short <branch>
      ├─ rev-list count:
      │    git rev-list --count --since="<days> days ago" <branch>
      └─ normalize → InsightsReport
```

### 13.3. Hotspots

- `changes` — число коммитов, где путь появился в `--name-only`; один коммит
  считается один раз на путь (дедупликация внутри коммита).
- Merge-коммиты исключены: они дублируют изменения из PR и раздувают churn.
- Топ-5 (`INSIGHTS_HOTSPOTS_LIMIT`), сортировка `changes desc, path asc`.
- `share = changes / total_commits_analyzed`; `authors` и `last_commit`
  собираются из тех же строк лога (author/date).
- Rename detection отключён: `--name-only` показывает новое имя только с
  момента переименования. Это осознанное ограничение (стоимость `-M` на
  больших историях), фиксируется в UI/доках.
- Битые/удалённые файлы остаются в статистике как исторические пути.

### 13.4. DORA-lite

- `deployment_frequency` — **прокси**: коммиты в ветке за окно, не реальные
  деплои. UI явно подписывает «commit frequency».
- `commits` включает merge-коммиты (каждый push в `main` — потенциальный
  деплой); `merge_commits` отдаётся отдельно.
- `sparkline`: daily при `days ≤ 90`, weekly при 91–365; нулевые бакеты
  заполняются, чтобы график не «склеивал» даты.
- `per_day`/`per_week` — производные, округление до 2 знаков.

### 13.5. Ограничения и деградация

- `status=no_branch` — ветка не определена; `shallow_clone` — есть
  `.git/shallow`, числа могут быть занижены; `timeout` — git не успел;
  `unavailable` — ошибка Git.
- Пустая история — валидный `ok` с пустыми списками.
- In-memory кэш 300 с, ключ `repo_id + branch + days`; `refresh=true` обходит.
- Ограничение stdout защищает память на репозиториях с сотнями тысяч файлов.

### 13.6. Read-only

- Только `git log` и `git rev-list`; `fetch`, `checkout`, `reset`, `clean`
  отсутствуют (grep-аудит).
- `GIT_OPTIONAL_LOCKS=0` предотвращает случайную запись lock-файлов.
- Рабочая директория и индекс не изменяются; анализ не требует сети.

---

## 14. Collaboration export (v0.6.0, Sprint 30 — план)

### 14.1. Markdown Export

- Чистая функция `buildDashboardMarkdown(snapshot)` на клиенте: вход — текущий
  срез (summary, отфильтрованные репозитории, видимые колонки).
- Выход — GFM: заголовок, дата, счётчики, таблица, список «требуют внимания».
- Экранирование `|` и перевода строк в ячейках; HTML не генерируется.
- Копирование — `navigator.clipboard.writeText`, fallback через скрытый
  `textarea`; серверный эндпоинт не добавляется.

### 14.2. Workspace Export/Import

```
{version: 1, exported_at, app_version,
 views: [...],
 table: {visible_columns, column_order, widths}}
```

- Экспорт собирается из Zustand store (`useViewsStore`, `useTableStore`);
  токены/секреты/данные репозиториев не входят.
- Импорт: лимит 1 MiB → `JSON.parse` → проверка `version` и структуры →
  нормализация полей → `replace` или `merge` по имени view.
- Ошибка валидации не меняет store; пользователь видит сообщение.
- Ключи `views.v1` и `table.state.v1` остаются прежними; миграции store
  переиспользуются, отдельного формата хранения нет.
- После импорта store обновляется реактивно, без перезагрузки страницы.

---

## 15. Что ещё не сделано (v0.7+)

- Синхронизация saved views в БД между устройствами (v0.7.0; в v0.6.0 — только
  файловый export/import).
- История статусов (trend: как часто репозиторий был `dirty`; как часто `behind_gitflic`).
- Полноценный GitFlic Compare API (сейчас — compare внутри GitFlic, классификация по SHA/датам).
- Docker lifecycle-операции (start/stop/restart/logs) — вне scope v0.6.0.
- Транзитивные зависимости, lock-файлы, SBOM и лицензионный аудит.
- Полное сканирование истории Git на секреты (gitleaks/trufflehog).
- Приватные registry и аутентификация в PyPI/npm, OSV Enterprise.
- Остальные DORA-метрики (lead time, change failure rate, MTTR).
