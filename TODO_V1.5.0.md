# TODO v1.5.0 — Global Analytics & IaC Scanning

**Статус:** Sprint 62 — планирование завершено; Sprint 63 — реализован
(v1.4.3); S63-Fix-4 — реализован (v1.4.4); спринты 64–65 — запланированы.
**База:** v1.4.4 «RAG Settings & Diagnostics» (раздельные `model_name` и
`embedding_model`, настройки RAG в UI, проверка размерности).
**Цель:** дать сводную картину технического долга по всем tracked-репозиториям
и добавить read-only аудит инфраструктурных файлов (`Dockerfile`,
`docker-compose.yml`) без запуска Docker, сборки образов и исполнения кода.

**Источники истины:** [`docs/SPEC.md`](docs/SPEC.md),
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md),
[`docs/RULES.md`](docs/RULES.md).

> **Важно:** спринт 62 — только документация и планирование. Код приложения в
> этом спринте не меняется.

---

## 1. Принципы v1.5.0

- **Read-only по умолчанию.** Агрегация статистики и IaC-анализ только читают
  рабочую директорию и существующие кэши. Новых мутаций, commit/push, запуска
  `docker build`, `docker run`, `docker compose` и установки пакетов нет.
- **Агрегаты не тормозят дашборд.** `GlobalStatsService` строит ответ из
  существующих отчётов/кэшей (`repository_status`, `dependency_cache`,
  `security_cache`, отчёты `IacService`) и кэширует результат in-memory.
  Тяжёлые проверки не запускаются синхронно на каждый запрос.
- **Честный partial result.** Недоступный репозиторий, устаревший кэш или
  ошибка парсинга не скрывают остальные данные: HTTP 200, проблемная запись
  получает `partial`/`error`/`unknown` и понятную причину.
- **IaC — только локальный текст.** `Dockerfile` разбирается построчным
  state-machine (regex + продолжения строк), `docker-compose*.yml` —
  безопасным YAML-парсером. Docker daemon, registry и сеть не используются.
- **Никаких новых зависимостей.** Используются существующие `recharts`,
  PyYAML, `ai_cache`, `dependency_cache`/`security_cache`. Новая зависимость
  возможна только через ADR.
- **AI — только по агрегатам.** Глобальный AI-отчёт получает counts, имена
  репозиториев и топ проблем; код, diff, пути вне репозитория, токены и
  секреты в промпт не попадают.
- **ADR first.** До реализации фиксируются ADR-0023 «Global stats aggregation
  & caching» и ADR-0024 «IaC scanning policy».
- **Без изменений state-модели.** `current/behind/ahead/diverged/dirty/...`
  (SPEC §3.4) не меняются; агрегаты только читают существующие состояния.

**Вне scope v1.5.0:** автоматическое исправление Dockerfile/compose,
генерация Dockerfile, запуск контейнеров и образов, проверка актуальности
базовых образов через registry API, полноценный Dockerfile AST/парсер,
Kubernetes/Terraform/Ansible, policy-engine (OPA/Conftest), приватные
registry, автоматическое создание PR с исправлениями IaC.

---

## 2. Sprint 62 — Planning (S62-001..S62-003)

**Цель:** зафиксировать контракты глобальной аналитики и IaC до написания
кода.

- [x] **S62-001. Roadmap:** `TODO_V1.5.0.md` — спринты 63–65, контракты,
      лимиты, риски, трассировка на SPEC/ARCHITECTURE.
- [x] **S62-002. Документация:** SPEC §3.34 (global-stats + AI advice),
      §3.35 (IaC + global-iac), ARCHITECTURE §33–§34, KI-026, анонс v1.5.0
      в README.
- [x] **S62-003. DoD и консистентность:** Definition of Done для каждого
      спринта; контракты не противоречат §3.6/§3.19/§3.32 и не меняют
      state-модель; ссылки TODO ↔ SPEC ↔ ARCHITECTURE ↔ KNOWN_ISSUES
      проверены.

**DoD Sprint 62:**

- [x] `TODO_V1.5.0.md` создан в корне и содержит спринты 63–65 с DoD.
- [x] В SPEC добавлены `GET /dashboard/global-stats`,
      `POST /dashboard/global-stats/ai-advice`,
      `GET /repositories/{id}/iac` и `GET /dashboard/global-iac`.
- [x] ARCHITECTURE описывает `GlobalStatsService` (кэш, single-flight,
      источники) и `IacService` (Dockerfile state-machine, compose YAML).
- [x] KI-026 добавлена; счётчик проблем обновлён.
- [x] README Roadmap содержит анонс v1.5.0 (Global Analytics, IaC Scanning).
- [x] Код приложения не менялся (только документация).

---

## 3. Sprint 63 — Global Tech Debt Dashboard (план)

**Цель:** на одном экране показать, сколько технического долга накопилось во
всех tracked-репозиториях: outdated-пакеты, CVE, dirty-файлы, diverged-ветки,
и какие 5 репозиториев «горят» сильнее всего.

### 3.1. Backend: `GlobalStatsService`

**Новый модуль:** `backend/app/services/global_stats_service.py`.

**Источники данных (только чтение):**

| Показатель | Источник | Свежесть |
|------------|----------|----------|
| `outdated_packages` | `DependencyService.get_report(ecosystem="all")` + `dependency_cache` | кэш реестра 24 ч |
| `vulnerabilities` | `SecurityService.get_report()` + `security_cache` | кэш OSV 6 ч |
| `dirty_files` | `repository_status` (modified + staged + untracked + conflicted) | `STATUS_TTL_SECONDS` |
| `diverged_branches` | `repository_status.state == "diverged"` | `STATUS_TTL_SECONDS` |
| `iac_issues` | `IacService` (появляется в Sprint 64; до этого `0`) | кэш IaC 5 мин |

- Агрегация выполняется только для `repositories.tracked=true`. Нет
  tracked-репозиториев → пустой отчёт `summary` с нулями, HTTP 200.
- `DependencyService`/`SecurityService` вызываются с `refresh=false`; при
  отсутствии свежего кэша используется stale-значение с пометкой `stale=true`.
  `refresh=true` на `/dashboard/global-stats` передаётся в источники и
  обновляет только истёкшие записи (concurrency ≤
  `GLOBAL_STATS_CONCURRENCY`, default 4).
- `outdated_packages` — количество **экземпляров** пакетов
  (`repository_id + ecosystem + name`) со `status="outdated"`; дополнительно
  `unique_outdated_packages` — уникальные `ecosystem:name`.
- `vulnerabilities` — количество advisory-записей с разбивкой по severity
  (`critical|high|medium|low|unknown`); `unique_cves` — уникальные
  `osv_id`/CVE. Дубли одного advisory в разных репозиториях считаются
  экземплярами, а не уникальными CVE.
- `diverged_branches` — число tracked-репозиториев в состоянии `diverged`
  (в текущей модели у репозитория одна отслеживаемая ветка).
- `problem_score` для репозитория (детерминированная формула):
  `outdated * 1 + critical * 10 + high * 5 + medium * 2 + low * 1 +
  unknown * 1 + dirty_files * 1 + diverged * 5 + iac_critical * 10 +
  iac_high * 5 + iac_medium * 2 + iac_low * 1`.
- `top_problematic` — до `GLOBAL_STATS_TOP_LIMIT` (default 5) репозиториев по
  `problem_score` desc, затем `name` asc. Полный список — в `repositories[]`.
- Ошибка одного репозитория/источника → запись `status="partial"` или
  `status="error"`, `errors[]`, HTTP 200. Ошибка всех источников → HTTP 200 с
  нулями и `error="all_sources_unavailable"` (не 500).
- Read-only: сервис не вызывает `git fetch`, не сканирует диск заново, не
  пишет в репозитории и не меняет `repository_status`.

### 3.2. API: `GET /api/v1/dashboard/global-stats`

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

- `scope.repositories` — все репозитории, `scope.tracked` — `tracked=true`,
  `scope.scanned` — хотя бы один источник ответил, `scope.skipped` — tracked,
  но ни один источник не ответил (`status=error`).
- `status ∈ {ok, partial, error}`; `partial` — хотя бы один источник
  недоступен/устарел, `error` — репозиторий не читается.
- `stale=true` — использовано значение из кэша с истёкшим TTL.
- `repositories[]` сортируется по `problem_score` desc, `name` asc; полей
  `label`/локализованных строк в API нет (локализация — на фронтенде).
- In-memory кэш ответа `GLOBAL_STATS_CACHE_TTL_SECONDS` (default **300** =
  5 мин), single-flight: параллельные запросы ждут один расчёт.
  `refresh=true` обходит кэш. После Sprint 64 `iac_issues` заполняется из
  `IacService`; до этого всегда `0` (поле additive, не ломает контракт).
- Метрики Prometheus: `global_stats_duration_seconds`,
  `global_stats_cache_hits_total`, `global_stats_partial_total`.
- Ошибки: `422` — неверный `refresh`; отдельных 404 нет.

### 3.3. AI Insights: общий отчёт по кодовой базе

| Метод | Путь | Тело | Параметры | Ответ |
|-------|------|------|-----------|-------|
| POST | `/api/v1/dashboard/global-stats/ai-advice` | `{language?: "ru"\|"en"}` | `refresh?: bool` | `GlobalStatsAdvice` |

**`GlobalStatsAdvice`:** `{generated_at, summary, priorities[],
model, cached}`.

- В LLM отправляются только агрегаты `GlobalStatsReport`, имена/алиасы
  репозиториев и их счётчики. Пути, код, diff, имена пакетов с версиями,
  CVE-описания, токены и секреты не отправляются.
- `priorities[]` — до 5 записей `{title, reason, repository_id, action}`;
  `summary` ≤ 2000 символов; `action` — текстовая рекомендация, не команда.
- Промпт и `state_hash` строятся по `summary + top_problematic`; изменение
  счётчиков инвалидирует `ai_cache`.
- Ключ `ai_cache`: `global-stats-advice:<state_hash>:<model>:<prompt_version>:<language>`,
  TTL `AI_CACHE_TTL_SECONDS` (default 7 дней). `refresh=true` обходит кэш;
  `X-AI-Cache: hit|miss`.
- `LLM_ENABLED=false`, remote-guard или ошибка LLM → `503 ai_unavailable`;
  ошибки LLM не кэшируются. Тело необязательно; без тела — `language="ru"`.
- `auditor` имеет доступ (read-only AI, как остальные AI-эндпоинты).

### 3.4. Frontend: «Tech Debt Overview»

- Новый блок на главном дашборде (не отдельный тяжёлый роут): карточки
  «Outdated», «CVE (High/Critical)», «Dirty files», «Diverged», «IaC issues»
  (последняя — `0` до Sprint 64) + две диаграммы:
  - **Pie Chart** по `summary.problem_types` (доли типов проблем);
  - **Bar Chart** по `top_problematic` (топ-5 репозиториев по `problem_score`).
- Клик по карточке/сегменту/бару ведёт к отфильтрованному списку репозиториев
  или к деталям репозитория. Пустое состояние — «Технический долг не найден»;
  `partial` — бейдж «Часть данных недоступна» с tooltip причин.
- Графики — в lazy-chunk (как существующие charts); entry bundle остаётся
  **< 90 kB gzip**. Новых runtime-зависимостей нет.
- AI-панель «Что горит»: кнопка «Сгенерировать отчёт», индикатор
  `X-AI-Cache`, 503-сообщение «AI недоступен», RU/EN, `aria-live` для
  результата.
- A11y: клавиатурная навигация по карточкам, `aria-label` у диаграмм,
  текстовое описание данных, контраст M3.
- RU/EN-словари: `dashboard.globalStats.*`, `dashboard.aiInsights.*`;
  числа/даты через `Intl`.

**DoD Sprint 63:**

- [x] `GlobalStatsService`: агрегация tracked-репозиториев, partial/stale,
      `problem_score`, `top_problematic`, single-flight, TTL 300 с.
- [x] `GET /dashboard/global-stats` + Pydantic-схемы `GlobalStatsReport`,
      `GlobalRepositoryStats`; контракт совпадает со SPEC §3.34.
- [x] `POST /dashboard/global-stats/ai-advice`: `ai_cache`, 503 при LLM off,
      лимит 2000 символов, промпт без кода/секретов.
- [x] Интеграционные тесты на реальных tmp-репозиториях: outdated/CVE из
      кэша, dirty/diverged, отсутствие tracked, частичная ошибка, кэш/refresh,
      single-flight, AI 503/hit/miss.
- [x] UI: карточки + Pie/Bar, lazy charts, empty/partial/error, RU/EN, `aria`,
      клики к фильтрам/деталям; entry bundle < 90 kB gzip.
- [x] Read-only: тест `git status --porcelain` до/после запроса не меняется;
      `fetch` не вызывается.
- [x] Prometheus-метрики и structlog-события без путей/секретов.
- [x] ADR-0023 «Global stats aggregation & caching».
- [x] `ruff`, `mypy --strict`, `pytest -q`, frontend typecheck/lint/test/build
      — зелёные.

---

## 4. Sprint 64 — Infrastructure as Code (IaC) Scanning (план)

**Цель:** находить рискованные настройки контейнеров в `Dockerfile` и
`docker-compose.yml`, не запуская Docker и не изменяя файлы.

### 4.1. Backend: `IacService`

**Новый модуль:** `backend/app/services/iac_service.py`.

**Обнаружение файлов (только рабочая директория):**

| Файлы | kind |
|-------|------|
| `Dockerfile`, `Dockerfile.*`, `*.Dockerfile` | `dockerfile` |
| `docker-compose.yml`, `docker-compose.yaml`, `compose.yml`, `compose.yaml` | `compose` |

- Глубина `IAC_MAX_DEPTH` (default **3**) от корня репозитория; исключаются
  `.git/`, `node_modules/`, `.venv/`, `vendor/`, `dist/`, `build/`, `target/`.
- Лимиты: `IAC_MAX_FILES` (default **100**) файлов на репозиторий,
  `IAC_MAX_FILE_BYTES` (default **1048576** = 1 MiB), `IAC_MAX_FINDINGS`
  (default **200**). Превышение → `truncated=true`, `status=partial`.
- Symlink'и не разыменовываются; файлы вне корня репозитория игнорируются.
- Файлы только читаются; `docker`, `docker compose`, registry и сеть не
  используются. `GIT_OPTIONAL_LOCKS=0`.

### 4.2. Парсер Dockerfile

- Построчный **state-machine**, а не один regex: нормализация BOM/CRLF,
  склейка продолжений строк (`\` в конце, кроме комментариев), игнор
  комментариев `#`, инструкции case-insensitive.
- Отслеживается текущий stage (`FROM ... AS alias`), финальный stage
  оценивается для `USER`/`HEALTHCHECK`; учитываются multi-stage сборки.
- `USER` — последний в stage; `USER root`, `USER 0`, `USER root:root` →
  root. `USER ${VAR}` не угадывается: правило root-user не срабатывает
  (избегаем false positive; см. KI-026).
- `FROM scratch` не требует `USER` (нет passwd/пользователей).
- `HEALTHCHECK NONE` трактуется как отсутствие healthcheck.
- Базовый образ: `FROM` без тега/digest или `:latest` → `IAC003`
  («unpinned/outdated base»). Проверка «вышла ли новая версия образа» через
  registry API — вне scope v1.5.0 (нет сети).
- Ошибка чтения/разбора файла → `file.status="parse_error"`, остальные файлы
  продолжают обрабатываться.

### 4.3. Парсер docker-compose

- YAML через `yaml.safe_load` с лимитом размера; никаких custom constructors,
  тегов `!!python/*` и выполнения кода. Ошибка YAML → `parse_error`.
- Лимит сервисов на файл — **200**; глубина/алиасы YAML ограничены размером
  файла.
- Поддерживаются короткая (`"8080:80"`, `"127.0.0.1:8080:80"`) и длинная
  (`{target, published, host_ip, protocol}`) формы `ports`.
- `privileged`, `network_mode`, `volumes` читаются только как данные; ничего
  не запускается.

### 4.4. Правила

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

- `severity ∈ {critical, high, medium, low, unknown}` — та же шкала, что у
  CVE/SAST.
- `message` — короткое описание; `evidence` ≤ 300 символов (строка/фрагмент
  YAML), секреты маскируются; `remediation` — текстовая рекомендация.
- `fingerprint = sha256(rule_id + file + line + normalized_evidence)`;
  дубли схлопываются.
- `IAC001`/`IAC002` проверяют каждый Dockerfile, но findings дедуплицируются
  по fingerprint; для нескольких stage — только финальный stage.

### 4.5. API: `GET /api/v1/repositories/{id}/iac`

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/api/v1/repositories/{id}/iac` | `refresh?: bool (default false)` | `IacReport` |

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

- `status ∈ {ok, partial, no_files, parse_error, unavailable}`:
  `no_files` — IaC-файлы не найдены (HTTP 200); `partial` — часть файлов
  не разобрана/превышен лимит; `parse_error` — все найденные файлы не
  разобраны; `unavailable` — репозиторий недоступен.
- `files[]` — все найденные файлы (включая `parse_error`), сортировка по
  пути; `findings[]` — по severity desc (`critical→unknown`), затем
  `file`, `line`.
- In-memory кэш `IAC_CACHE_TTL_SECONDS` (default **300**), ключ
  `repo_id + head_sha + dirty_hash + file_mtimes`; `refresh=true` обходит
  кэш. Недоступный/`parse_error` результат не кэшируется.
- Read-only и offline: нет Docker daemon, нет registry, нет сети; тест
  `git status --porcelain` до/после не меняется.
- Ошибки: `404 repository_not_found`; `422` — неверный `refresh`.
  Недоступность файлов отражается в отчёте, а не HTTP 500.
- UI: блок «Инфраструктура» в деталях репозитория (рядом с SAST/CVE):
  severity, `file:line`, message, evidence, remediation, empty-state
  «IaC-файлы не найдены», `aria`, RU/EN, lazy-загрузка.

### 4.6. API: `GET /api/v1/dashboard/global-iac`

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/api/v1/dashboard/global-iac` | `refresh?: bool (default false)` | `GlobalIacReport` |

**`GlobalIacReport`:** `{checked_at, cached, summary, repositories[],
top_findings[], errors[], error}`.

- Агрегация по всем `tracked=true`: `summary` — сумма severity по всем
  отчётам; `repositories[]` — `{repository_id, name, path, files_scanned,
  critical, high, medium, low, unknown, total, status, error}`;
  `top_findings[]` — до `IAC_GLOBAL_TOP_LIMIT` (default **10**) записей
  `{repository_id, name, rule_id, severity, file, line, message}`.
- Кэш `GLOBAL_IAC_CACHE_TTL_SECONDS` (default **300**), concurrency ≤
  `IAC_CONCURRENCY` (default 4), single-flight; `refresh=true` обходит кэш.
- Ошибка одного репозитория → `status="partial"`/`error` в его записи,
  HTTP 200; ошибка всех → HTTP 200 с нулями и `error="all_repositories_failed"`.
- На дашборде Sprint 63 `summary.iac_issues` берётся из этого отчёта
  (количество findings severity `high|critical`), начиная с Sprint 64.
- UI: компактная сводка «Инфраструктура» на дашборде (critical/high/medium),
  переход к топ-находкам/репозиторию, RU/EN, `aria`.

**DoD Sprint 64:**

- [ ] `IacService` + `DockerfileParser` (state-machine, continuations,
      multi-stage, `scratch`) и `ComposeParser` (`yaml.safe_load`, лимиты).
- [ ] Правила IAC001–IAC008, severity, fingerprint, дедупликация,
      `truncated`, `parse_error`/`partial`.
- [ ] `GET /repositories/{id}/iac` + `IacReport`; `GET /dashboard/global-iac` +
      `GlobalIacReport`; контракты совпадают со SPEC §3.35.
- [ ] Интеграция `iac_issues` в `GlobalStatsReport` (Sprint 63-контракт
      расширяется additive-полем, без breaking changes).
- [ ] Тесты на реальных tmp-репозиториях: root/non-root/`USER ${VAR}`,
      `HEALTHCHECK`/`NONE`, `latest`/digest, multi-stage, `scratch`,
      privileged, public/localhost ports, host network, docker.sock,
      битый YAML, лимиты, вложенные файлы, symlink, `IAC_ENABLED=false`,
      отсутствие записи.
- [ ] UI: блок «Инфраструктура» + глобальная сводка, severity, `file:line`,
      remediation, empty/partial/error, RU/EN, `aria`, lazy.
- [ ] Read-only: нет Docker daemon/сети; `git status --porcelain` не меняется;
      `docker`/registry не вызываются.
- [ ] ADR-0024 «IaC scanning policy» (offline, regex/state-machine,
      false positives, лимиты).
- [ ] `ruff`, `mypy --strict`, `pytest -q`, frontend typecheck/lint/test/build
      — зелёные; entry bundle < 90 kB gzip.

---

## 5. Sprint 65 — Release v1.5.0 (план)

- [ ] Финальный аудит read-only: нет новых destructive-команд, `docker build`/
      `docker run`/`docker compose`, записи в репозитории и сетевых вызовов
      IaC-парсеров.
- [ ] Версии `1.5.0` в `backend/app/config.py`, `backend/app/__init__.py`,
      `backend/pyproject.toml`, `frontend/package.json`,
      `frontend/src-tauri/tauri.conf.json`, `frontend/src-tauri/Cargo.toml`.
- [ ] `docs/CHANGELOG.md` (1.5.0), `docs/RELEASES.md`, README, SPEC,
      ARCHITECTURE согласованы; KI-026 остаётся актуальной или закрыта с
      обоснованием.
- [ ] Новых миграций нет (in-memory кэши); проверить, что схема БД не
      изменилась, и SQLite/PostgreSQL-пути не деградировали.
- [ ] Smoke: global-stats на 20+ tracked-репозиториях, partial/stale,
      AI-отчёт (LLM on/off), IaC на Python/Node/.NET-проектах с Dockerfile и
      compose, пустой репозиторий, битый compose.
- [ ] Тег `v1.5.0` запускает кросс-платформенный Release (Windows/macOS/Linux);
      артефакты, `.sig` и `latest.json` проверены.
- [ ] Push в `origin` и `gitflic`, зеркалирование релиза.
- [ ] Обновить README: версия, статус, счётчики тестов/bundle, roadmap.

**DoD Sprint 65:** все пункты выше выполнены; релиз `v1.5.0` опубликован;
`TODO_V1.5.0.md` переведён в статус «выпущен».

---

## 6. Контракты и совместимость

| Объект | Контракт | Совместимость |
|--------|----------|---------------|
| `GlobalStatsReport` | `{checked_at, cached, scope, summary, repositories[], top_problematic[], errors[], error}` | новый; `GET /dashboard` и `GET /dashboard/global-dependencies` не меняются |
| `problem_score` | детерминированная формула из §3.1 | новый; используется только для сортировки/топа |
| `GlobalStatsAdvice` | `{generated_at, summary, priorities[], model, cached}` | новый; использует существующий `ai_cache` |
| `IacReport` | `{repository_id, checked_at, status, files[], summary, findings[], truncated, error, cached}` | новый; `SecurityReport`/`SastReport` не меняются |
| `GlobalIacReport` | `{checked_at, cached, summary, repositories[], top_findings[], errors[], error}` | новый |
| `iac_issues` | additive-поле в `GlobalStatsReport.summary` | до Sprint 64 — `0`; после — число high/critical IaC-findings |
| `GLOBAL_STATS_*` | env-переменные §5 SPEC | новые, defaults безопасны |
| `IAC_*` | env-переменные §5 SPEC | новые, defaults безопасны |
| state-модель | `current/behind/ahead/diverged/dirty/...` | **не меняется** |

**Трассировка:**

| Требование | SPEC | ARCHITECTURE | Спринт |
|------------|------|--------------|--------|
| Глобальная статистика долга | §3.34 | §33 | 63 |
| AI-отчёт по всей базе | §3.34.2 | §33.3 | 63 |
| IaC: Dockerfile/compose | §3.35 | §34 | 64 |
| Глобальная IaC-сводка | §3.35.2 | §34.5 | 64 |
| Ложные срабатывания парсинга | §3.35 | §34.6 (KI-026) | 64 |
| Релиз v1.5.0 | §8 | — | 65 |

---

## 7. Риски и зависимости

| Риск | Влияние | Митигация |
|------|---------|-----------|
| Агрегация по 30+ репозиториям тормозит дашборд | Медленный первый запрос, таймауты | кэш 300 с + single-flight + concurrency 4; источники читают кэши, не сеть |
| Устаревшие `dependency_cache`/`security_cache` | Ложная «хорошая» картина | `stale=true`, бейдж «данные устарели», `refresh=true` |
| Ошибка одного репозитория | Пустой/неполный дашборд | partial HTTP 200, `errors[]`, `error` у записи |
| Dockerfile-парсер регулярками | Ложные/пропущенные findings | state-machine, multi-stage, `USER ${VAR}` не угадывается, KI-026, тесты на реальных файлах |
| YAML-бомбы/небезопасный YAML | DoS/выполнение кода | `safe_load`, лимит 1 MiB, 200 сервисов, без custom tags |
| `ports` в compose трактуются неверно | Ложный critical/high | поддержка short/long form, `host_ip`, тесты на `127.0.0.1`/`0.0.0.0`/random port |
| Docker registry недоступен | Нельзя проверить «устарел ли FROM» | scope: только unpinned/`:latest`, без сетевого registry |
| AI получает лишние данные | Утечка кода/секретов | только агрегаты/имена, allowlist полей, тесты промпта |
| Bundle растёт из-за графиков | Нарушение бюджета | lazy charts, entry < 90 kB gzip, budget-check |
| Новые env-переменные ломают конфиг | Ошибка старта | defaults, `.env.example`, валидация Settings |
| `auditor` запускает тяжёлые проверки | Нагрузка на сервер | `refresh` остаётся read-only; кэш 300 с, concurrency 4 и лимиты; аудит не пишется, новых мутаций нет |

**Зависимости:** `recharts` (уже есть), PyYAML (уже есть), существующие
`DependencyService`, `SecurityService`, `IacService`, `ai_cache`. Новых
Python/npm-зависимостей нет.

---

## 8. Итог спринта 62

- Roadmap v1.5.0 зафиксирован; спринты 63–65 имеют измеримые DoD.
- Контракты API, кэширования, лимитов и AI-промпта описаны до кода.
- Архитектура не противоречит текущим SPEC §3.6/§3.19/§3.32 и
  ARCHITECTURE §16/§30; state-модель не меняется.
- Следующий шаг — Sprint 63: `GlobalStatsService` + `GET /dashboard/global-stats`
  + UI «Tech Debt Overview».
