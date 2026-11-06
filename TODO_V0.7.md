# TODO v0.7.0 — AI Integration, Global Analytics & Dependency Updates

**Версия:** v0.7.0 «AI & Global Analytics»
**Статус:** ✅ Завершён (Sprint 34, релиз `v0.7.0`)
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

**Статус:** ✅ Завершён (2026-11-06)

**Задачи**

- [x] **S32-001. LLM-клиент и конфигурация.**
  - `app/services/llm_service.py`: OpenAI-совместимый
    `POST {base_url}/chat/completions`, `httpx`, без новых зависимостей.
  - LM Studio (`http://127.0.0.1:1234/v1`) — default; Ollama
    (`http://127.0.0.1:11434/v1`) поддерживается; `provider` определяется по URL.
  - `LLM_ENABLED` (default false), `LLM_BASE_URL`, `LLM_MODEL`,
    `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS` (default 30),
    `LLM_MAX_DIFF_CHARS` (default 10000), `LLM_ALLOW_REMOTE` (default false).
  - Ошибки: timeout, connection refused, 4xx/5xx, невалидный JSON → `None`
    без исключения наружу; remote endpoint блокируется без opt-in.

- [x] **S32-002. Settings UI и API.**
  - `GET/PATCH /settings` расширены `llm_enabled`, `llm_base_url`,
    `llm_model`, `llm_api_key`, `llm_timeout_seconds`, `llm_max_diff_chars`,
    `llm_allow_remote`; bool/int значения корректно применяются к `config.py`.
  - `llm_api_key` маскируется (`sk-****1234`); пустое поле — «не менять».
  - Страница Settings: секция «AI / LLM» (enabled, endpoint, model, key,
    timeout, max diff, allow_remote) с предупреждением о remote endpoint.

- [x] **S32-003. Diff builder и генерация сообщения.**
  - Diff строится в API через `get_worktree_diff`:
    `git diff HEAD --no-color --no-ext-diff --unified=3`;
    untracked не входят; бинарники не дают текстового diff.
  - `LLMService.generate_commit_message(diff) -> str | None`; timeout 30 с;
    лимит `LLM_MAX_DIFF_CHARS` (10000), при обрезке добавляется
    `[diff truncated]`, `truncated=true`, `warnings=["diff_truncated"]`.
  - Промпт: Conventional Commits (feat/fix/docs/refactor), «ответь только
    текстом коммита, без кавычек»; markdown-обёртки/кавычки снимаются.
  - Fallback-сообщение не генерируется: ошибка LLM → `503`, UI показывает toast.

- [x] **S32-004. API и ActionLog commit.**
  - `POST /repositories/{id}/ai/commit-message` → `CommitMessageSuggestion`
    по SPEC §3.18.1; пустой diff → `400`, LLM off/remote → `409`,
    LLM недоступна → `503`.
  - `commit` добавлен в whitelist `ActionService`:
    `POST /repositories/{id}/actions/commit` с `confirm=true` и `message`
    (≤ 2000 символов), запись в `action_log`.
  - Diff и промпт не сохраняются и не логируются.

- [x] **S32-005. UI-модалка «Сгенерировать коммит».**
  - Кнопка в карточке репозитория только при `dirty.modified/staged > 0` и
    `llm_enabled=true` (флаг из `GET /settings`).
  - Модалка: spinner, редактируемый `<textarea>`, «Скопировать»,
    «Выполнить коммит» (только после чекбокса подтверждения).
  - Ошибка LLM — toast «LLM недоступна. Проверьте настройки.»;
    автоматического коммита из AI-эндпоинта нет.

- [x] **S32-006. Тесты и документация.**
  - `test_llm.py`: успешная генерация, timeout/connection/5xx, disabled,
    remote-guard, API 400/409/503, truncation, commit action, settings mask.
  - SPEC §3.18 (фактические поля), ARCHITECTURE §15, ADR-0010,
    CHANGELOG/RELEASES. Секретов в диффе нет.

**DoD:**

- [x] `POST /repositories/{id}/ai/commit-message` соответствует SPEC §3.18.1.
- [x] LLM-клиент работает с Ollama и LM Studio через OpenAI-совместимый API;
      timeout ≤ 30 с, ошибки → `503`, без 500.
- [x] Diff ограничен `LLM_MAX_DIFF_CHARS`; бинарники не отправляются;
      diff/промпт не попадают в логи и БД.
- [x] Remote endpoint блокируется без `LLM_ALLOW_REMOTE=true`.
- [x] Сообщение возвращается в редактируемой модалке; автоматического коммита нет.
- [x] `commit` требует `confirm=true` и непустое сообщение; пишется `action_log`.
- [x] Settings маскирует API-ключ; секреты не попадают в дифф/логи.
- [x] Тесты, `ruff`, `mypy --strict`, frontend-проверки — зелёные.

---

### Спринт 33 — AI Security Insights & Global Dashboard

**Статус:** ✅ Завершён (2026-11-06)

**Задачи**

- [x] **S33-001. CVE explain.**
  - `POST /repositories/{id}/ai/cve-explain` с телом `{cve_id, summary}`.
  - Промпт: «Ты — эксперт по безопасности… в чем опасность уязвимости
    {cve_id}… Как её исправить? Ответь кратко, 2-3 предложения.»
  - `security_cache`/OSV не запрашиваются: summary приходит из `SecurityReport`.
  - Кэш `ai_cache` (ключ `cve-explain:<cve_id>:<model>`, TTL 7 дней);
    `cached=true` при попадании.
  - `409 llm_disabled`/`llm_remote_not_allowed`; LLM недоступна → `503`,
    fallback-текст не подставляется.

- [x] **S33-002. Global Analytics Service.**
  - `app/services/global_analytics_service.py`: `tracked=true` репозитории,
    `DependencyService.get_report(ecosystem="all")` (существующие парсеры).
  - Агрегация по `<ecosystem>:<name>`: `distribution` (версия → проекты),
    `latest_version`, `versions_count`, `projects_count`.
  - `unification_needed = versions_count > 1`; сортировка `projects_count` desc,
    `name` asc; `GLOBAL_ANALYTICS_LIMIT` (default 50).
  - In-memory кэш 1 час; `refresh=true` обходит и передаётся в
    `DependencyService`; concurrency ≤ 4; partial failure → `partial_errors`.

- [x] **S33-003. API `GET /dashboard/global-dependencies`.**
  - Параметр `refresh?: bool`; ответ `GlobalDependencyReport` по SPEC §3.19
    (`ecosystems: {python: [...], node: [...]}`), отсутствие манифестов —
    пустые массивы, а не 404/500.

- [x] **S33-004. UI: объяснение CVE и глобальный дашборд.**
  - В блоке «Безопасность» — кнопка «Объяснить» (при `llm_enabled`); модалка
    со спиннером, текстом объяснения и ошибкой LLM.
  - Блок «Global Dependencies» на дашборде: таблица пакетов, ecosystem,
    `latest_version`, распределение версий, бейдж «Унифицировать», refresh.
  - Пустые/частичные состояния; никаких мутаций.

- [x] **S33-005. Тесты и документация.**
  - `test_global_analytics.py`: реальные tmp-проекты, агрегация, лимит,
    сортировка, кэш, API.
  - `test_ai_explain.py`: prompt, успех, ошибка, disabled, API и кэш.
  - SPEC §3.18.2/§3.19, ARCHITECTURE §15.4/§16, CHANGELOG/RELEASES.

**DoD:**

- [x] `POST /repositories/{id}/ai/cve-explain` соответствует SPEC §3.18.2.
- [x] Объяснение кэшируется в `ai_cache` на 7 дней; LLM off/remote → `409`,
      LLM недоступна → `503`.
- [x] `GET /dashboard/global-dependencies` соответствует SPEC §3.19;
      агрегация по tracked-репозиториям и лимит работают.
- [x] `distribution`/`unification_needed` детерминированы; partial failure
      отражается как `partial_errors`.
- [x] Кэш ответа 1 час; `refresh=true` обходит кэш.
- [x] UI: explain-модалка и глобальная таблица, пустые/частичные состояния.
- [x] Тесты, `ruff`, `mypy --strict`, frontend-проверки — зелёные.
- [x] Документация и KI-013 обновлены.

---

### Спринт 34 — Automated Dependencies & Release v0.7.0

**Статус:** ✅ Завершён (2026-11-06, релиз `v0.7.0`)

**Задачи**

- [x] **S34-001. Dependency update service.**
  - `app/services/dependency_update_service.py`: preflight и запуск CLI через
    `asyncio.create_subprocess_exec`.
  - Python: `pip install -r requirements.txt --upgrade` (через текущий
    интерпретатор); Node: `pnpm update` при `pnpm-lock.yaml`, иначе `npm update`.
  - Preflight: `confirm=true`; `git status --porcelain` пуст, иначе `409`
    `Worktree must be clean`; менеджер/манифест определены (`no_manifest`).
  - Timeout `DEPENDENCY_UPDATE_TIMEOUT_SECONDS` (default 180), output cap
    `DEPENDENCY_UPDATE_MAX_OUTPUT_CHARS` (10000), redaction credentials.
  - Любая попытка (успех/ошибка/отказ) пишется в `action_log`
    (`action=update-dependencies`, `actor=local|bulk`).

- [x] **S34-002. API обновления.**
  - `POST /repositories/{id}/actions/update-dependencies` →
    `ActionLog`; тело `{confirm, ecosystem: python|node}`.
  - `POST /repositories/actions/update_dependencies_all` →
    `202 {status:"accepted"}`, фон, `repo_ids?`, concurrency 2.
  - Ошибка обновления не даёт 500: `409`/`ActionLog.status=error` с причиной.

- [x] **S34-003. UI обновления пакетов.**
  - Кнопка «Обновить пакеты» в блоке «Зависимости», disabled при
    `state="dirty"`/`no_manifest` с подсказкой.
  - Модалка подтверждения: изменит `requirements.txt`/`package.json`/lockfile.
  - После успеха — toast «Зависимости обновлены», refresh статуса и отчёта;
    ошибка dirty/manager показывается в модалке.

- [x] **S34-004. ADR и тесты.**
  - ADR-0011 «Explicit, preflight-checked dependency updates».
  - `test_dependency_updates.py`: clean/dirty preflight, python/node detection,
    timeout/redaction, `action_log`, API 400/409/202.
  - UI-тесты disabled/modal/update.

- [x] **S34-005. Финальный аудит и релиз v0.7.0.**
  - Версии `0.7.0`, CHANGELOG, RELEASES, README, SPEC, TODO_V0.7.
  - `docs/prompts/docs-consistency-audit.md`: SPEC ↔ ARCHITECTURE ↔ README ↔ KI.
  - Проверки: `ruff`, `mypy --strict`, `pytest -q`,
    `pnpm typecheck && lint && test && build`.
  - Тег `v0.7.0` в GitHub и GitFlic; `SHA(main)` совпадает; GitHub Release.

**DoD:**

- [x] `POST /repositories/{id}/actions/update-dependencies` и bulk-вариант
      соответствуют SPEC §3.9/§3.20.
- [x] Обновление невозможно без `confirm=true` и на грязном дереве
      (`409 "Worktree must be clean"`), отказ тоже попадает в `action_log`.
- [x] Определение менеджера корректно: pip / pnpm / npm; ошибка менеджера —
      `ActionLog.status=error`, без 500.
- [x] Timeout ≤ 180 с, вывод ограничен 10000 символов и очищен от токенов.
- [x] UI: подтверждение, предупреждения, обработка dirty-состояния,
      отсутствие автозапуска.
- [x] ADR-0011 и KI-014 обновлены; read-only вне явного действия сохранён.
- [x] Все проверки зелёные; docs-consistency audit пройден.
- [x] Тег `v0.7.0` в обоих провайдерах, `SHA(main)` совпадает.

---

## 4. Контракты v0.7.0 (сверка со SPEC/ARCHITECTURE)

| Контракт | Источник истины |
|----------|-----------------|
| `POST /repositories/{id}/ai/commit-message`, `CommitMessageSuggestion` | `docs/SPEC.md` §3.18.1 |
| `POST /repositories/{id}/ai/cve-explain`, `CveExplanation` | `docs/SPEC.md` §3.18.2 |
| `GET /dashboard/global-dependencies`, `GlobalDependencyReport` | `docs/SPEC.md` §3.19 |
| `POST .../actions/update-dependencies`, bulk 202, `dirty_worktree` | `docs/SPEC.md` §3.9, §3.20 |
| Settings `llm_*` и маскировка ключа | `docs/SPEC.md` §3.12 |
| `LLMService`, таймауты, remote-guard | `docs/ARCHITECTURE.md` §15; ADR-0010 |
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
