# TODO v0.6.0 — Security, Insights & Collaboration

**Версия:** v0.6.0 «Security, Insights & Collaboration»
**Статус:** 🚧 В разработке (Sprint 28 ✅); спринты 29–30 запланированы
**Предыдущий этап:** v0.5.0 — [`TODO_V0.5.md`](TODO_V0.5.md)
**Последнее обновление:** 2026-11-06

---

## 1. Цели v0.6.0

| # | Цель | Критерий достижения |
|---|------|---------------------|
| G1 | Видеть уязвимости в своих зависимостях | Список CVE из OSV.dev для Python/Node с severity; High/Critical видны сразу |
| G2 | Не коммитить секреты | Regex-сканер находит AWS/GitHub/JWT-паттерны в рабочей директории и показывает файл:строку |
| G3 | Понимать, где копится технический долг | Топ-5 файлов по churn за окно анализа в карточке репозитория |
| G4 | Оценивать ритм поставки | Commit frequency в `main` за 30 дней + sparkline (DORA-lite) |
| G5 | Делиться состоянием проекта | Сводка в Markdown в один клик; перенос Saved Views/колонок между устройствами через JSON |
| G6 | Сохранить read-only и предсказуемый релиз | Никаких установок/обновлений пакетов и записи в репозиторий; DoD, тесты, docs-consistency audit, тег `v0.6.0` |

---

## 2. Принципы

1. **Маленькие итерации:** спринт = законченная порция, `main` всегда зелёный.
2. **Read-only по умолчанию:** security/insights только читают файлы и Git-историю; пакеты не обновляются, секреты не редактируются автоматически.
3. **Один факт — один источник:** SPEC — контракты, ARCHITECTURE — устройство, этот файл — план.
4. **Деградация без падения:** недоступный OSV.dev, таймаут `git log`, shallow clone — это состояние (`unavailable`/`partial`), а не 500.
5. **Кэш — часть контракта:** TTL и ключи кэша фиксируются в SPEC/ARCHITECTURE.
6. **Секреты не логируются:** ни полные значения, ни содержимое файлов; только маскированный preview.
7. **Никаких новых зависимостей без ADR:** HTTP — существующий `httpx`; regex — stdlib `re`; Git-лог — уже используемый `git` CLI.
8. **A11y и тема — в DoD:** новые блоки проверяются в light/dark и с клавиатуры.

---

## 3. Спринты

### Спринт 27 — Планирование v0.6.0 (✅ Завершён)

- [x] **S27-001:** создать `TODO_V0.6.md` с декомпозицией спринтов 28–30.
- [x] **S27-002:** обновить `docs/SPEC.md` (§3.16–3.17, §4, §5, §6, §8, §9),
  `docs/ARCHITECTURE.md` (§1–2, §12–14), `docs/KNOWN_ISSUES.md` (KI-011/012),
  `README.md` (Roadmap), `TODO.md` (актуальный этап и матрица KI).
- [x] **S27-003:** зафиксировать DoD каждого спринта и сверить контракты
  эндпоинтов со SPEC/ARCHITECTURE.

**DoD:** документы согласованы между собой; код приложения не менялся; план
содержит измеримые критерии и явные границы scope.

---

### Спринт 28 — Supply Chain Security

**Статус:** ✅ Завершён (2026-11-06)

**Задачи**

- [x] **S28-001. OSV.dev клиент.**
  - `app/providers/osv_client.py`: `POST {OSV_API_URL}/v1/query` (один пакет) и
    `POST /v1/querybatch` (пакет), тело `{package: {name, ecosystem}, version}`.
  - Ecosystem: `PyPI` для `requirements.txt`, `npm` для `package.json`.
  - Timeout `SECURITY_HTTP_TIMEOUT=10`, User-Agent `IIRuchating/0.6`,
    concurrency ≤ `SECURITY_CHECK_CONCURRENCY=4`.
  - 429/5xx — backoff 0.5/1/2 с (max 3 попытки); 400/404 по пакету — не роняет
    отчёт. Ошибки клиента → `unavailable`, не 500.

- [x] **S28-002. SecurityService: CVE.**
  - Переиспользовать парсеры v0.5.0 (`requirements.txt`, `package.json`), не
    дублировать чтение манифестов; `pip`/`npm` не запускаются.
  - Разрешение версии: `exact` → declared; `range` → нижняя граница с
    `version_source=lower_bound`; неразрешимый диапазон → `unknown`, пакет
    попадает в `unknown_packages`, а не в «чистые».
  - Маппинг severity: CVSS v3 ≥ 9.0 → `critical`, 7.0–8.9 → `high`,
    4.0–6.9 → `medium`, < 4.0 → `low`; без CVSS — severity из OSV, иначе
    `unknown`.
  - Дедупликация по `osv_id`; агрегирование `cve_ids`/`aliases`; `fixed_version`
    из `affected.ranges[].events[].fixed`.
  - Кэш `security_cache` (ключ `osv:<ecosystem>:<package>:<version>`, TTL
    `SECURITY_CACHE_TTL_SECONDS=21600` = 6 ч); stale-while-revalidate.
  - Фильтр `min_severity` (default `high`); сортировка: severity desc, package asc.

- [x] **S28-003. Secret Scanner (базовый).**
  - Источник файлов: `git ls-files -z -co --exclude-standard` (tracked +
    untracked, кроме ignored). История Git **не** сканируется.
  - Пропускать: бинарные файлы, размер > `SECRET_SCAN_MAX_FILE_BYTES` (1 MiB),
    `.git/`, `node_modules/`, `.venv/`, `vendor/`, `dist/`, `build/`,
    `target/`; лимит `SECRET_SCAN_MAX_FILES=5000`.
  - Правила (regex, только stdlib `re`): AWS Access Key ID
    (`AKIA[0-9A-Z]{16}`), AWS secret key (assignment), GitHub token
    (`gh[pousr]_[A-Za-z0-9]{36,}`), JWT (`eyJ...\.eyJ...`), private key header
    (`-----BEGIN ... PRIVATE KEY-----`).
  - Ложные срабатывания: строка-маркер `# iiruchating:ignore-secret` и
    `?include_secrets=false` (KI-012). В ответе — только `preview`
    (`ghp_****1234`), никогда полное значение.
  - In-memory кэш `SECRET_SCAN_TTL_SECONDS=300`; `refresh=true` обходит оба кэша.

- [x] **S28-004. API `GET /api/v1/repositories/{id}/security`.**
  - Параметры `refresh?: bool`, `include_secrets?: bool (default true)`,
    `min_severity?: critical|high|medium|low|all (default high)`.
  - Ответ `SecurityReport` по SPEC §3.16; отсутствие манифеста —
    `status=no_manifest`, а не 404/500.
  - Частичный отчёт: ошибка OSV по одному ecosystem не скрывает второй и секреты.

- [x] **S28-005. UI-блок «Безопасность».**
  - Бейджи `critical/high/medium/low`, пакет, установленная версия → `fixed`,
    CVE/GHSA-ссылки, раскрываемый список.
  - Секреты: файл:строка, тип, severity, маскированный preview; пустое
    состояние «Секретов не найдено».
  - Состояния `unavailable`/`partial`/`no_manifest` читаемы; блок lazy,
    кнопка «Проверить снова» → `?refresh=true`. Действий «исправить» нет.

- [x] **S28-006. Тесты и документация.**
  - Тесты: fake OSV-клиент (severity, дедупликация, backoff, 404/429/5xx),
    `version_source`, фильтр `min_severity`, кэш/refresh, partial failure.
  - Secret scanner: фикстуры каждого правила, бинарники/большие файлы,
    ignore-маркер, отсутствие полного секрета в ответе и логах.
  - ADR-0009 «OSV.dev + regex secret scanning without package-manager
    execution»; SPEC/ARCHITECTURE/KNOWN_ISSUES (KI-011/012)/CHANGELOG.

**DoD:**

- [x] `GET /repositories/{id}/security` соответствует SPEC §3.16.
- [x] Python и Node проверяются; exact-версии дают CVE, range помечается
      `lower_bound`, неразрешимые — `unknown` (не «чисто»).
- [x] По умолчанию отдаются High/Critical; `min_severity=all` возвращает всё.
- [x] Секреты: в ответе/логах только маскированный preview; история Git не
      сканируется; лимиты файлов/размера соблюдаются.
- [x] OSV 429/5xx/timeout → `unavailable`/partial, HTTP 200; stale-кэш
      используется, если есть.
- [x] Read-only: рабочая директория и индекс не меняются; `pip`/`npm` не
      вызываются; destructive-команд нет (grep-аудит).
- [x] Тесты, `ruff`, `mypy --strict`, frontend-проверки — зелёные.
- [x] ADR-0009 и документация обновлены; секретов в диффе нет.

---

### Спринт 29 — Tech Debt & Insights

**Статус:** ⏳ Запланирован

**Задачи**

- **S29-001. Git-log runner для InsightsService.**
  - `asyncio.create_subprocess_exec` (или `asyncio.to_thread`) с `cwd=repo.path`,
    `GIT_OPTIONAL_LOCKS=0`; только `git log` / `git rev-list`.
  - Таймаут `INSIGHTS_GIT_TIMEOUT_SECONDS=10`; при превышении процесс
    kill'ится, ответ `status=timeout` — event loop не блокируется.
  - Ограничение размера stdout (например, 8 MiB) и числа строк; ошибки Git не
    дают 500.
  - Определение ветки: upstream → `main` → `master` → текущая ветка HEAD.

- **S29-002. Hotspots.**
  - `git log --since=<days> --no-merges --name-only --pretty=format:` в окне
    (default 30 дней, max 365).
  - `changes` = число коммитов, затронувших путь (не строк diff); топ-5 по
    `changes` desc, при равенстве — `path` asc; `share` = changes / сумма.
  - Переименования не отслеживаются (`--name-only`, без rename detection) —
    ограничение фиксируется в документации.
  - Пустая история → `files=[]`, `status=ok`; shallow clone → `shallow_clone`.

- **S29-003. DORA-lite (Deployment Frequency).**
  - `git rev-list --count <branch> --since=<window>`; `merge_commits` считается
    отдельно (`--merges`), `commits` включает все коммиты ветки.
  - Sparkline: `git log --format=%ad --date=short --since=<window>`; bucket =
    `day` для окон ≤ 90 дней, `week` для 91–365; пустые дни заполняются нулём.
  - `per_day` / `per_week` — производные, округление до 2 знаков.
  - Это **прокси** частоты поставки, а не фактический deploy-трекинг; явно
    указывается в ответе и UI.

- **S29-004. API `GET /api/v1/repositories/{id}/insights`.**
  - Параметры `days?: int (default 30, 1..365)`, `refresh?: bool`.
  - Ответ `InsightsReport` по SPEC §3.17; in-memory кэш
    `INSIGHTS_CACHE_TTL_SECONDS=300`, ключ `repo_id + branch + days`.

- **S29-005. UI-блок «Инсайты».**
  - Топ-5 «горячих» файлов: путь (mono, обрезка + tooltip), число изменений,
    относительная полоса.
  - Sparkline commit frequency за окно + подпись «за 30 дней, прокси DORA».
  - Пустые/частичные состояния; блок lazy; кнопка «Обновить».

- **S29-006. Тесты и документация.**
  - Тесты на tmp-репозиториях: детерминированные истории, топ-5 и tie-break,
    merge-коммиты, пустая ветка, shallow clone, timeout (fake).
  - SPEC/ARCHITECTURE/CHANGELOG; отметить ограничения rename/shallow.

**DoD:**

- [ ] `GET /repositories/{id}/insights` соответствует SPEC §3.17.
- [ ] Event loop не блокируется: Git-вызовы асинхронные, таймаут ≤ 10 с,
      зависший `git` не вешает API.
- [ ] Hotspots детерминированы, top-5 по умолчанию, merge-коммиты исключены.
- [ ] DORA-lite считает коммиты в ветке за окно; ветка и `merge_commits`
      отражены в ответе; sparkline заполняет пустые дни.
- [ ] Пустой репозиторий / нет ветки / shallow clone → состояние, не 500.
- [ ] Read-only: только `git log`/`git rev-list`; нет fetch/checkout/reset
      (grep-аудит).
- [ ] Кэш 300 с и `refresh=true`; entry bundle в бюджете (блок lazy).
- [ ] Тесты, `ruff`, `mypy --strict`, frontend-проверки — зелёные.

---

### Спринт 30 — Collaboration & Release v0.6.0

**Статус:** ⏳ Запланирован

**Задачи**

- **S30-001. Markdown Export.**
  - Кнопка «Скопировать сводку в Markdown» на дашборде; формирование на клиенте
    из текущего среза (фильтры и видимые колонки учитываются).
  - Содержимое: заголовок, дата, `summary` (всего/чистые/требуют внимания/
    не отслеживаются), таблица репозиториев (имя, ветка, state, ahead/behind,
    mirror) и список «требуют внимания».
  - Валидный GFM: экранирование `|` в путях/именах; копирование в clipboard +
    toast; серверный эндпоинт не добавляется.

- **S30-002. Workspace Export/Import.**
  - Экспорт JSON: `{version: 1, exported_at, app_version, views,
    table: {visible_columns, column_order, widths}}`; скачивание файла.
  - Импорт: выбор файла, проверка размера (≤ 1 MiB), JSON-схемы и `version`;
    несовместимая версия — понятная ошибка, состояние не меняется.
  - Режим `replace` (по умолчанию) или `merge` по имени view; токены, фильтры
    с секретами и данные репозиториев **не** экспортируются.
  - Экспорт/импорт не затрагивает `localStorage`-ключи других версий
    (`views.v1`, `table.state.v1`).

- **S30-003. Финальный аудит и релиз v0.6.0.**
  - Версии `0.6.0` (backend `app_version`, frontend `package.json`),
    CHANGELOG, RELEASES, README, SPEC, TODO_V0.6.
  - `docs/prompts/docs-consistency-audit.md`: SPEC ↔ ARCHITECTURE ↔ README ↔ KI.
  - Проверки: `ruff`, `mypy --strict`, `pytest -q`,
    `pnpm typecheck && lint && test && build`, Docker Compose smoke.
  - Тег `v0.6.0` в GitHub и GitFlic; `SHA(main)` совпадает; GitHub Release.

**DoD:**

- [ ] Markdown-сводка копируется, является валидным GFM и отражает активные
      фильтры; `|` экранирован; HTML не инжектится.
- [ ] Export/import round-trip сохраняет views и настройки колонок; невалидный
      JSON/размер/версия → ошибка без изменения состояния.
- [ ] В экспортируемом JSON нет токенов, секретов и содержимого репозиториев.
- [ ] Все проверки зелёные; docs-consistency audit пройден.
- [ ] CHANGELOG/RELEASES/README/SPEC отражают фактическое поведение.
- [ ] Тег `v0.6.0` есть в обоих провайдерах, `SHA(main)` совпадает.

---

## 4. Контракты v0.6.0 (сверка со SPEC/ARCHITECTURE)

| Контракт | Источник истины |
|----------|-----------------|
| `GET /repositories/{id}/security`, `SecurityReport`, severity/статусы | `docs/SPEC.md` §3.16 |
| `GET /repositories/{id}/insights`, `InsightsReport`, hotspots/DORA | `docs/SPEC.md` §3.17 |
| Таблица `security_cache`, TTL 6 ч | `docs/SPEC.md` §4, §5; `docs/ARCHITECTURE.md` §12.5 |
| OSV.dev, версии из диапазонов, severity mapping | `docs/ARCHITECTURE.md` §12; `docs/adr/0009-supply-chain-security.md` |
| Secret Scanning: источники файлов, лимиты, маскирование | `docs/ARCHITECTURE.md` §12.6; `docs/SPEC.md` §3.16.3 |
| Hotspots/DORA через subprocess, таймауты, кэш | `docs/ARCHITECTURE.md` §13 |
| Markdown export, Workspace export/import | `docs/SPEC.md` §9.11; `docs/ARCHITECTURE.md` §14 |
| Rate-limit OSV.dev и ложные срабатывания | `docs/KNOWN_ISSUES.md` KI-011, KI-012 |

---

## 5. Сквозной Definition of Done

- [ ] Все задачи спринта `[x]` или явно перенесены в `KNOWN_ISSUES` с `KI-NNN`.
- [ ] `ruff check backend/app backend/tests` — 0.
- [ ] `mypy backend/app` — 0.
- [ ] `pytest -q` — passed (покрытие ≥ 70% для новых сервисов).
- [ ] `pnpm --dir frontend typecheck && pnpm --dir frontend lint && pnpm --dir frontend test` — 0.
- [ ] `pnpm --dir frontend build` — 0; entry bundle ≤ 100 kB gzip, новые блоки lazy.
- [ ] Новые контракты отражены в SPEC; устройство — в ARCHITECTURE.
- [ ] Read-only: нет установки/обновления пакетов, записи в репозиторий,
      fetch/checkout/reset; destructive-команд нет (grep-аудит).
- [ ] Секреты не попадают в логи, ответы и диффы; в ответе только masked preview.
- [ ] `docs/RELEASES.md` — отчёт по спринту; `docs/CHANGELOG.md [Unreleased]` обновлён.
- [ ] Для релизного спринта — docs-consistency audit и тег в обоих провайдерах.

---

## 6. Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| OSV.dev rate-limit / нет SLA | Высокая | Среднее | KI-011: кэш 6 ч, concurrency 4, backoff, partial results, stale-кэш |
| Ложные срабатывания Secret Scanner | Высокая | Среднее | KI-012: маскирование, ignore-маркер, `include_secrets=false`, severity/confidence |
| Сканирование файлов «читает» секреты в память | Средняя | Высокое | Никогда не логировать совпадения; только preview; лимиты файлов/размера; local-only |
| Диапазоны версий не дают точного CVE-ответа | Высокая | Среднее | `version_source=lower_bound`/`unknown`; не выдавать «чисто» без проверки |
| `git log --name-only` на огромных репозиториях | Средняя | Среднее | Таймаут 10 с, kill процесса, кэш 300 с, `--no-merges`, лимит stdout |
| Shallow clone искажает hotspots/DORA | Средняя | Низкое | Детект `.git/shallow` → `status=shallow_clone` |
| Переименования файлов ломают историю churn | Средняя | Низкое | Явное ограничение `--name-only` без rename detection |
| Импорт повреждённого/огромного JSON | Средняя | Среднее | Лимит 1 MiB, валидация схемы/версии, состояние не меняется при ошибке |
| Рост bundle из-за новых блоков | Средняя | Среднее | lazy-загрузка, бюджет 100 kB gzip |
| Токены/секреты попадают в экспорт workspace | Низкая | Высокое | Экспорт только views/columns; тест «в JSON нет токенов» |

---

## 7. Вне scope v0.6.0

- Полное сканирование истории Git на секреты (gitleaks/trufflehog, все блобы).
- Локальная база advisories, SBOM, лицензионная проверка зависимостей.
- Автоматическое обновление/исправление уязвимых пакетов, PR-боты.
- Транзитивные зависимости и lock-файлы (по-прежнему вне scope).
- DORA lead time / change failure rate / MTTR — только commit-frequency прокси.
- Серверная синхронизация Saved Views между устройствами (только файл).
- Управление секретами (хранение/ротация), интеграция с secret managers.
- CI-интеграция security-сканов и блокирующие гейты в pipeline.
