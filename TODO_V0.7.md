# TODO v0.7.0 — AI Integration, Global Analytics & Dependency Updates

**Версия:** v0.7.0 «AI & Global Analytics»
**Статус:** 🚧 Планирование (Sprint 31); спринты 32–34 запланированы
**Предыдущий этап:** v0.6.0 — [`TODO_V0.6.md`](TODO_V0.6.md)
**Последнее обновление:** 2026-11-06

---

## 1. Цели v0.7.0

| # | Цель | Критерий достижения |
|---|------|---------------------|
| G1 | Локальный AI без утечки кода | Ollama/LM Studio через OpenAI-совместимый API; по умолчанию только loopback |
| G2 | Быстрый черновик коммита | По `git diff` генерируется Conventional Commits-сообщение; пользователь подтверждает в модалке |
| G3 | Понятные CVE | По клику — объяснение уязвимости на русском, основанное только на данных OSV |
| G4 | Единая картина зависимостей | Глобальный дашборд: версии популярных пакетов, устаревшие и кандидаты на унификацию |
| G5 | Управляемое обновление пакетов | Обновление только по явному подтверждению, на чистом дереве, с аудитом `action_log` |
| G6 | Деградация без падения | LLM недоступен → fallback-черновик/сводка; OSV/реестр недоступен → partial report |
| G7 | Предсказуемый релиз | DoD каждого спринта, тесты, docs-consistency audit, тег `v0.7.0` |

---

## 2. Принципы

1. **Local-first AI.** По умолчанию `LLM_BASE_URL` указывает на loopback
   (Ollama/LM Studio). Не-loopback endpoint требует явного
   `LLM_ALLOW_REMOTE=true`.
2. **AI — помощник, не источник истины.** CVE-объяснения строятся только на
   данных OSV; сгенерированный commit message — черновик, который подтверждает
   пользователь.
3. **Read-only по умолчанию.** Генерация коммита и объяснение CVE ничего не
   меняют. Обновление пакетов — отдельное действие с `confirm=true`.
4. **Секреты не уходят в LLM-логи.** Diff и промпты не логируются; `llm_api_key`
   маскируется. Пользователь предупреждён, что diff может содержать секреты.
5. **Один факт — один источник.** SPEC — контракты, ARCHITECTURE — устройство,
   этот файл — план, ADR — причины решений.
6. **Маленькие итерации:** спринт = законченная порция, `main` всегда зелёный.
7. **Никаких новых зависимостей без ADR.** HTTP — существующий `httpx`;
   обновления пакетов — через уже установленные CLI.

---

## 3. Спринты

### Спринт 31 — Планирование v0.7.0 (✅ Завершён)

- [x] **S31-001:** создать `TODO_V0.7.md` с декомпозицией спринтов 32–34.
- [x] **S31-002:** обновить `docs/SPEC.md` (§1, §3.12, §3.18–3.20, §4, §5,
  §6.4, §8, §9.12), `docs/ARCHITECTURE.md` (§1–2, §15–17),
  `docs/KNOWN_ISSUES.md` (KI-013/014), `README.md`, `TODO.md`,
  `docs/RULES.md`, `SECURITY.md`.
- [x] **S31-003:** зафиксировать DoD каждого спринта и сверить контракты
  эндпоинтов со SPEC/ARCHITECTURE.

**DoD:** документы согласованы между собой; код приложения не менялся; план
содержит измеримые критерии и явные границы scope.

---

### Спринт 32 — LLM Provider & AI Commit Messages

**Статус:** ⏳ Запланирован

**Задачи**

- **S32-001. LLM-клиент и конфигурация.**
  - `app/providers/llm_client.py`: OpenAI-совместимый
    `POST {base_url}/chat/completions`, `httpx`, без новых зависимостей.
  - Поддержать Ollama (`http://127.0.0.1:11434/v1`) и LM Studio
    (`http://127.0.0.1:1234/v1`); `provider` определяется по URL/настройке.
  - `LLM_ENABLED` (default false), `LLM_BASE_URL`, `LLM_MODEL`,
    `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS` (default 30),
    `LLM_MAX_DIFF_BYTES` (default 65536), `LLM_ALLOW_REMOTE` (default false).
  - Ошибки: timeout, connection refused, 4xx/5xx, невалидный JSON — результат
    со статусом, без исключения наружу.
  - Circuit breaker: после 3 подряд ошибок — пауза 60 с, затем fallback.

- **S32-002. Settings UI и API.**
  - Расширить `GET/PATCH /settings` полями `llm_enabled`, `llm_base_url`,
    `llm_model`, `llm_api_key`, `llm_timeout_seconds`, `llm_allow_remote`.
  - `llm_api_key` маскируется (`sk-****1234`); пустое поле — «не менять».
  - Страница Settings: секция «AI / LLM» с проверкой соединения
    (кнопка «Проверить»; отдельный контракт не добавляется) и понятным
    предупреждением о remote endpoint.

- **S32-003. Diff builder и генерация сообщения.**
  - `LLMService.build_commit_message(repo_path, ...)`:
    - `git diff HEAD --no-color --no-ext-diff --unified=3` (staged + unstaged);
    - бинарные файлы и untracked (по умолчанию) исключаются;
    - лимит `max_diff_bytes`, обрезка по границе файла, `truncated=true`.
  - Промпт: Conventional Commits, subject ≤ 72 символов, опциональное тело;
    diff считается **данными**, инструкции внутри diff игнорируются.
  - Валидация ответа: regex `^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?: .+`;
    Markdown-обёртки снимаются; невалидный ответ → fallback.
  - Fallback без LLM: `chore: update N files` + список групп файлов,
    `source=fallback`, `warnings`.

- **S32-004. API `POST /repositories/{id}/ai/commit-message`.**
  - Тело: `{include_untracked?: bool (default false), max_diff_bytes?: int}`.
  - Ответ `CommitMessageSuggestion` по SPEC §3.18; `source ∈ {llm, fallback}`.
  - `422 no_changes` — нет tracked-изменений; `409 llm_disabled` — LLM выключен.
  - Diff и промпт не сохраняются и не логируются.

- **S32-005. UI-модалка «Сгенерировать коммит».**
  - Кнопка в карточке репозитория только при `dirty.modified/staged > 0` и
    `llm_enabled=true`.
  - Лоадер с таймаутом, отмена; результат — модалка с subject/body, кнопкой
    «Скопировать» и пометкой `fallback`/`truncated`.
  - Никакого автоматического `git commit`.

- **S32-006. Тесты и документация.**
  - Fake LLM client: успешный ответ, timeout, 5xx, невалидный ответ,
    fallback, обрезка diff, отсутствие изменений.
  - SPEC §3.18, ARCHITECTURE §15, ADR-0010 «Local-first LLM integration»,
    CHANGELOG/RELEASES. Секретов в диффе нет.

**DoD:**

- [ ] `POST /repositories/{id}/ai/commit-message` соответствует SPEC §3.18.
- [ ] LLM-клиент работает с Ollama и LM Studio через OpenAI-совместимый API;
      timeout ≤ 30 с, ошибки → fallback, HTTP 200.
- [ ] Diff ограничен `LLM_MAX_DIFF_BYTES`; бинарники не отправляются;
      diff/промпт не попадают в логи и БД.
- [ ] Remote endpoint блокируется без `LLM_ALLOW_REMOTE=true`.
- [ ] Ответ валидируется как Conventional Commits; невалидный → fallback.
- [ ] UI показывает модалку, копирование работает, автоматического коммита нет.
- [ ] Settings маскирует API-ключ; секреты не попадают в дифф/логи.
- [ ] Тесты, `ruff`, `mypy --strict`, frontend-проверки — зелёные.

---

### Спринт 33 — AI Security Insights & Global Dashboard

**Статус:** ⏳ Запланирован

**Задачи**

- **S33-001. CVE explain.**
  - `POST /repositories/{id}/ai/cve-explain` по SPEC §3.18.2.
  - Источник фактов: `security_cache` или `GET https://api.osv.dev/v1/vulns/{id}`;
    клиентский summary — только подсказка, не единственный источник.
  - Промпт: объяснить простым языком, не выдумывать факты, указать
    `fixed_version` и ссылки; ответ на русском (`locale=ru`) или английском.
  - Кэш `ai_cache` (ключ `cve-explain:<osv_id>:<locale>:<model>`, TTL 7 дней).
  - OSV/LLM недоступны → grounded summary из кэша, `source=fallback`, HTTP 200.

- **S33-002. Global Analytics Service.**
  - `app/services/global_analytics_service.py`: обойти `tracked=true` репозитории,
    распарсить `requirements.txt`/`package.json` существующими парсерами.
  - Агрегировать по `<ecosystem>:<normalized-name>`: версии, число репозиториев,
    `latest` из `dependency_cache`, `recommended_version = max(declared)`.
  - `unification ∈ {aligned, mixed, unknown}`; `status ∈ {current, outdated, unknown}`.
  - По умолчанию никаких сетевых вызовов; `refresh=true` обновляет stale-кэш через
    registry-клиенты с concurrency ≤ 4 и partial failure.
  - In-memory кэш ответа 60 с; лимит top-N пакетов.

- **S33-003. API `GET /dashboard/global-dependencies`.**
  - Параметры `ecosystem?: python|node|all`, `limit?` (default 20, 1..100),
    `outdated_only?`, `refresh?`.
  - Ответ `GlobalDependencyReport` по SPEC §3.19; отсутствие манифестов —
    пустые массивы, а не 404/500.

- **S33-004. UI: объяснение CVE и глобальный дашборд.**
  - В блоке «Безопасность» — кнопка «Объяснить» у каждой уязвимости; лоадер,
    модалка с объяснением, `fixed_version` и ссылками.
  - Новая страница/секция «Глобальные зависимости»: топ пакетов, распределение
    версий, бейджи `aligned/mixed/outdated`, фильтр «только устаревшие»,
    счётчики проектов.
  - Пустые/частичные состояния; блоки lazy; никаких мутаций.

- **S33-005. Тесты и документация.**
  - Fake LLM/OSV/registry: explain+кэш, fallback, агрегация версий, top-N,
    partial failure, API-контракты, UI-состояния.
  - SPEC §3.18.2/§3.19, ARCHITECTURE §15.4/§16, ADR-0010, KI-013.

**DoD:**

- [ ] `POST /repositories/{id}/ai/cve-explain` соответствует SPEC §3.18.2.
- [ ] Объяснение опирается на OSV и не выдумывает `fixed_version`/ссылки;
      кэш 7 дней, `refresh` не требуется.
- [ ] `GET /dashboard/global-dependencies` соответствует SPEC §3.19;
      агрегация по tracked-репозиториям, top-N и `outdated_only` работают.
- [ ] `unification`/`recommended_version` детерминированы; partial failure
      не скрывает второй ecosystem.
- [ ] Глобальный дашборд не делает N×registry запросов без `refresh=true`.
- [ ] UI: explain-модалка и глобальная страница, пустые/частичные состояния.
- [ ] Тесты, `ruff`, `mypy --strict`, frontend-проверки — зелёные.
- [ ] Документация и KI-013 обновлены.

---

### Спринт 34 — Automated Dependencies & Release v0.7.0

**Статус:** ⏳ Запланирован

**Задачи**

- **S34-001. Dependency update service.**
  - `app/services/dependency_update_service.py`: preflight и запуск CLI.
  - Python: `pip install --upgrade -r requirements.txt` или выбранные пакеты.
  - Node: `pnpm update` при `pnpm-lock.yaml`, иначе `npm update`.
  - Preflight: `confirm=true`; дерево чистое (нет modified/staged/conflicted,
    `state != dirty`), иначе `409 dirty_worktree`; менеджер определён.
  - Timeout `DEPENDENCY_UPDATE_TIMEOUT_SECONDS` (default 180), output cap 32 KiB,
    redaction токенов в URL/логах.
  - Любая попытка (успех/ошибка/отказ) пишется в `action_log`
    (`action=update-dependencies`, `actor=local|bulk`).

- **S34-002. API обновления.**
  - `POST /repositories/{id}/actions/update-dependencies` →
    `ActionLog`; тело `{confirm, ecosystem?, packages?}`.
  - `POST /repositories/actions/update_dependencies_all` →
    `202 {status:"accepted"}`, фон, `repo_ids?`, concurrency 1–2.
  - Ошибка обновления не даёт 500: `409`/`ActionLog.status=error` с причиной.

- **S34-003. UI обновления пакетов.**
  - Кнопка «Обновить пакеты» для выбранных проектов/репозитория.
  - Модалка подтверждения: что изменится (`requirements`/lockfile), требование
    чистого дерева, предупреждение о недетерминированных версиях.
  - Прогресс/результат, ссылка на `action_log`; при `dirty_worktree` — понятная
    ошибка без выполнения.

- **S34-004. ADR и тесты.**
  - ADR-0011 «Explicit, preflight-checked dependency updates».
  - Fake subprocess: clean/dirty preflight, python/node detection, timeout,
    redaction, action_log; bulk concurrency.
  - UI-тесты подтверждения и ошибок.

- **S34-005. Финальный аудит и релиз v0.7.0.**
  - Версии `0.7.0`, CHANGELOG, RELEASES, README, SPEC, TODO_V0.7.
  - `docs/prompts/docs-consistency-audit.md`: SPEC ↔ ARCHITECTURE ↔ README ↔ KI.
  - Проверки: `ruff`, `mypy --strict`, `pytest -q`,
    `pnpm typecheck && lint && test && build`, Docker Compose smoke.
  - Тег `v0.7.0` в GitHub и GitFlic; `SHA(main)` совпадает; GitHub Release.

**DoD:**

- [ ] `POST /repositories/{id}/actions/update-dependencies` и bulk-вариант
      соответствуют SPEC §3.9/§3.20.
- [ ] Обновление невозможно без `confirm=true` и на грязном дереве
      (`409 dirty_worktree`), отказ тоже попадает в `action_log`.
- [ ] Определение менеджера корректно: pip / pnpm / npm; ошибка менеджера —
      `ActionLog.status=error`, без 500.
- [ ] Timeout ≤ 180 с, вывод ограничен и очищен от токенов.
- [ ] UI: подтверждение, предупреждения, обработка `dirty_worktree`,
      отсутствие автозапуска.
- [ ] ADR-0011 и KI-014 обновлены; read-only вне явного действия сохранён.
- [ ] Все проверки зелёные; docs-consistency audit пройден.
- [ ] Тег `v0.7.0` в обоих провайдерах, `SHA(main)` совпадает.

---

## 4. Контракты v0.7.0 (сверка со SPEC/ARCHITECTURE)

| Контракт | Источник истины |
|----------|-----------------|
| `POST /repositories/{id}/ai/commit-message`, `CommitMessageSuggestion` | `docs/SPEC.md` §3.18.1 |
| `POST /repositories/{id}/ai/cve-explain`, `CveExplanation` | `docs/SPEC.md` §3.18.2 |
| `GET /dashboard/global-dependencies`, `GlobalDependencyReport` | `docs/SPEC.md` §3.19 |
| `POST .../actions/update-dependencies`, bulk 202, `dirty_worktree` | `docs/SPEC.md` §3.9, §3.20 |
| Settings `llm_*` и маскировка ключа | `docs/SPEC.md` §3.12 |
| `LLMService`, таймауты, fallback, remote-guard | `docs/ARCHITECTURE.md` §15; ADR-0010 |
| `GlobalAnalyticsService`, агрегация и кэш | `docs/ARCHITECTURE.md` §16 |
| Обновление пакетов, preflight, `action_log` | `docs/ARCHITECTURE.md` §17; ADR-0011 |
| `ai_cache`, TTL 7 дней | `docs/SPEC.md` §4, §5; `docs/ARCHITECTURE.md` §15.4 |
| Медленный/галлюцинирующий LLM | `docs/KNOWN_ISSUES.md` KI-013 |
| Конфликт обновления с локальными изменениями | `docs/KNOWN_ISSUES.md` KI-014 |

---

## 5. Сквозной Definition of Done

- [ ] Все задачи спринта `[x]` или явно перенесены в `KNOWN_ISSUES` с `KI-NNN`.
- [ ] `ruff check backend/app backend/tests` — 0.
- [ ] `mypy backend/app` — 0.
- [ ] `pytest -q` — passed (покрытие ≥ 70% для новых сервисов).
- [ ] `pnpm --dir frontend typecheck && pnpm --dir frontend lint && pnpm --dir frontend test` — 0.
- [ ] `pnpm --dir frontend build` — 0; entry bundle ≤ 100 kB gzip, AI/analytics-блоки lazy.
- [ ] Новые контракты отражены в SPEC; устройство — в ARCHITECTURE.
- [ ] Read-only: AI-генерация и аналитика не меняют репозиторий; обновление
      пакетов — только `confirm=true` + чистый worktree + `action_log`.
- [ ] Diff/промпты/API-ключи не попадают в логи, БД (кроме `ai_cache` текста
      объяснений) и диффы.
- [ ] `docs/RELEASES.md` — отчёт по спринту; `docs/CHANGELOG.md [Unreleased]` обновлён.
- [ ] Для релизного спринта — docs-consistency audit и тег в обоих провайдерах.

---

## 6. Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| LLM медленный/зависает | Высокая | Среднее | KI-013: timeout 30 с, circuit breaker, fallback, отмена в UI |
| LLM галлюцинирует commit/CVE | Высокая | Среднее | Валидация Conventional Commits; CVE — только grounded OSV + ссылки; пользователь подтверждает |
| Diff содержит секреты | Средняя | Высокое | Local-first, remote-guard, diff не логируется, предупреждение в UI |
| Утечка `llm_api_key` | Низкая | Высокое | Маскировка, `app_settings`, не экспортируется в workspace |
| Ollama/LM Studio недоступны | Высокая | Низкое | `503`-подобная деградация через fallback/HTTP 200, подсказка в Settings |
| 34+ репозитория × реестры = rate-limit | Высокая | Среднее | `dependency_cache`, top-N, `refresh` только по действию, concurrency 4 |
| Разные версии пакетов и диапазоны | Высокая | Среднее | `unification`, `recommended_version=max(declared)`, `unknown` вместо ложного «current» |
| Обновление ломает сборку/конфликтует с dirty | Высокая | Высокое | KI-014: preflight clean, confirm, ADR-0011, откат вручную; без auto-retry |
| `pip/pnpm` меняют lockfile/окружение | Средняя | Высокое | Явное предупреждение в UI, `action_log`, вывод команд, никаких destructive Git |
| Рост bundle из-за AI-модалок | Средняя | Низкое | lazy-загрузка, бюджет 100 kB gzip |

---

## 7. Вне scope v0.7.0

- Облачные LLM по умолчанию, передача кода на внешние сервисы без opt-in.
- Автоматический `git commit`/`push` после генерации сообщения.
- Агентные сценарии (LLM сам решает, какие команды выполнять).
- Полный dependency resolver / обновление транзитивных зависимостей.
- Автоматический откат обновлений и merge-конфликтов.
- Синхронизация Saved Views в БД (v0.8+).
- Остальные DORA-метрики, SBOM, лицензионный аудит.
