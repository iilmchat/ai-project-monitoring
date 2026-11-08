# CHANGELOG — История версий

## [Unreleased]

### Добавлено

- feat(deps): рекурсивный `ManifestDiscovery` — `requirements.txt`/`package.json` во вложенных каталогах (`backend/`, `frontend/`), ignore-лист и `DEPENDENCY_MANIFEST_MAX_DEPTH`; DependencyService и SecurityService используют общий слой (S35-001).
- feat(deps): `manifests[]` и `manifest_path` в отчётах, дедупликация пакетов (exact > range с версией > range), отображение манифестов в UI (S35-001).
- feat(api): `GET /repositories/{id}/readme` — H1 и версия из README; `GET /repositories/{id}/docs?path=...` — безопасное чтение Markdown внутри репозитория (S35-002).
- feat(ui): «визитка» проекта с названием/версией из README и модалка документации с внутренними ссылками и историей «Назад» (S35-002).
- fix(ui): блок «Рекомендации» поднят сразу после статуса; после подтверждённого действия статус обновляется до пересчёта рекомендаций (S35-003).
- feat(ui): сворачиваемые фильтры, скрытая по умолчанию аналитика, кликабельные карточки сводки с фильтрами, группа «Репозитории» (S36-001..S36-003, частично).
- feat(ui): человеческие подписи статусов/зеркал в фильтрах и графиках, tooltips для новых контролов (S36-003, частично).
- feat(ui): Global Dependencies — закладки «Все/Python/Node» со счётчиками и раскрываемый список проектов со ссылками на карточки (S37-001, S37-002 частично).
- feat(ui): бейдж «2 копии» в таблице и блок «Связанные репозитории» для клонов с одинаковым именем (например, `ai-teacher_python` в AI и GitFlic); remote/SHA-идентичность — Sprint 37.
- feat(i18n): собственный `LanguageProvider`/`useI18n` без новых зависимостей, словари RU/EN по доменам, `Intl` для дат и чисел, `document.lang`, сохранение выбора в `localStorage` (S36-004).
- feat(ui): переключатель RU/EN рядом с темой; переведены шапка, дашборд, настройки, карточка репозитория, статусы/зеркала, графики, Global Dependencies, README-модалка, Command Palette и горячие клавиши (S36-004).
- feat(ui): tooltips/aria для статусов, зеркал, CI, дублей, опасных действий и AI-настроек (S36-005, частично).
- fix(insights): commit frequency использует локальную дату, чтобы коммиты после локальной полуночи не выпадали из окна (найдено при полном прогоне тестов).
- feat(identity): `IdentityService` — нормализация `remote.origin.url` (https/ssh/scp, `.git`, регистр) и группировка дубликатов; `GET /dashboard/duplicates` (S37-001).
- feat(ai): `LLMService.advise_unification` и `POST /dashboard/global-dependencies/ai-advice`; промпт только по версиям/проектам, кэш `ai_cache` 7 дней (S37-002).
- feat(ui): кнопка «AI Совет» с поповером для пакетов с `unification_needed` (S37-002).
- feat(ui): блок «Унификация» в карточке проекта — версия у вас/в других проектах и кнопка «Обновить до X» через существующий update flow (S37-003).
- feat(ai): `POST /ai/dashboard-advice` — агрегаты состояния, outdated и high/critical CVE; 2–3 рекомендации от LLM, кэш `ai_cache` 1 час (S38-001).
- feat(ui): lazy-виджет «AI Дайджест» на дашборде с кнопкой «Сгенерировать» и Markdown-ответом (S38-001).
- feat(ai): `POST /repositories/{id}/ai/agent-task` — Markdown-задача для DSH/OpenCode по state/dirty/конфликтам/последним коммитам; lazy-модалка с копированием (S38-002/003).
- feat(settings): `POST /settings/llm/test` — ping модели и latency/error; кнопка «Проверить LLM» в настройках (S38-003).
- test(ai): `test_dashboard_advice.py`, `test_agent_task.py`, тест `/settings/llm/test` и UI-тест AI-дайджеста (S38-004).
- feat(ai): `AIProviderProfile` + миграция `009`; CRUD `/settings/ai-providers`, активация, маскировка ключей и перенос текущих `llm_*` в профиль по умолчанию (S39-001).
- feat(ai): `LLMService.resolve()` читает активный профиль из БД при каждом вызове; fallback на `config.py`, переключение без перезапуска (S39-002).
- feat(ui): список AI-провайдеров в настройках, lazy-модалка добавления/редактирования, активация/удаление, пустой ключ сохраняет старый (S39-003).
- test(ai): `test_ai_providers.py` — CRUD, маскировка, активация и переключение LLMService (S39-004).

### Документация

- docs(spec): §3.15 — вложенные манифесты, `manifests[]`, `manifest_path`; §3.21 — README/docs endpoints и лимиты (S35-001..S35-002).
- docs(architecture): §18 — ManifestDiscovery, README и безопасный просмотр документов (S35).
- docs(planning): `TODO_V0.8.md` — спринты 35–40, goals, contracts, best practices.

## [0.7.0] - 2026-11-06

AI-ассистент для локального разработчика: генерация commit message, объяснение
CVE, глобальный анализ зависимостей и безопасное обновление пакетов.

### Добавлено

- feat(ai): `LLMService` — OpenAI-совместимый клиент (LM Studio/Ollama), timeout 30 с, remote-guard, очистка Markdown/кавычек; ошибки → `None` (S32-001).
- feat(settings): `llm_enabled`, `llm_base_url`, `llm_model`, `llm_api_key` (маскируется), timeout, max diff и `llm_allow_remote` в `GET/PATCH /settings` и на странице настроек (S32-002).
- feat(api): `POST /repositories/{id}/ai/commit-message` — `git diff HEAD`, лимит 10000 символов с `[diff truncated]`, `CommitMessageSuggestion` (S32-003).
- feat(actions): действие `commit` с `confirm=true` и сообщением (≤ 2000 символов), запись в `action_log` (S32-004).
- feat(ui): кнопка «Сгенерировать коммит» для dirty-репозиториев, модалка с лоадером, редактируемым текстом, копированием и подтверждённым коммитом (S32-005).
- test(ai): успешная генерация, timeout/connection/5xx, disabled, remote-guard, API 400/409/503, truncation, commit action и маскировка ключа (S32-006).
- feat(ai): `LLMService.explain_cve` и `POST /repositories/{id}/ai/cve-explain` с кэшем `ai_cache` на 7 дней (S33-001..S33-002).
- feat(analytics): `GlobalAnalyticsService` — агрегация версий по tracked-репозиториям через `DependencyService`, `distribution`/`unification_needed`, кэш 1 час (S33-001).
- feat(api): `GET /dashboard/global-dependencies` с `refresh` (S33-003).
- feat(ui): блок «Global Dependencies» с таблицей версий и бейджем «Унифицировать»; кнопка «Объяснить» и модалка CVE в блоке безопасности (S33-004).
- test(analytics): реальные tmp-проекты, агрегация/лимит/кэш/API; CVE prompt, кэш и ошибки LLM (S33-005).
- feat(deps): `DependencyUpdateService` — `pip install -r requirements.txt --upgrade` / `pnpm update` / `npm update`, preflight по `git status --porcelain`, timeout 180 с, output cap 10000 символов (S34-001).
- feat(api): `POST /repositories/{id}/actions/update-dependencies` и bulk `202`; preflight `confirmation_required`/`no_manifest`/`"Worktree must be clean"`, аудит `action_log` (S34-002).
- feat(ui): кнопка «Обновить пакеты» (disabled на dirty worktree), модалка подтверждения, toast «Зависимости обновлены» и refresh статуса/отчёта (S34-003).
- test(deps): clean/dirty preflight, pip/pnpm detection, redaction/cap, timeout/error, API 400/409/202 и UI-подтверждение (S34-004).

### Документация

- docs(release): SPEC §3.9/§3.20/§5, ARCHITECTURE §17, ADR-0011, RELEASES/README, версия `0.7.0` (S34-005).

- docs(ai/analytics): SPEC §3.18.2/§3.19, ARCHITECTURE §15.4/§16, CHANGELOG/RELEASES (S33-005).

- docs(ai): SPEC §3.12/§3.18.1, ARCHITECTURE §15, ADR-0010, CHANGELOG/RELEASES (S32-006).
- docs(planning): план v0.7.0 — LLM (commit message, CVE explain), global dependencies, dependency updates; SPEC §3.18–3.20, ARCHITECTURE §15–17, KI-013/014 (S31-001..S31-003).

## [0.6.0] - 2026-11-06

Безопасность цепочки поставок (CVE, секреты), технический долг и активность
(Hotspots, DORA-lite), совместная работа (Markdown, Workspace export).

### Добавлено

- feat(security): `OsvClient` — batch-запросы к OSV.dev, CVSS v3 base score, нормализация advisories (S28-001).
- feat(security): `SecurityService` — CVE для `requirements.txt`/`package.json`, `version_source=exact|lower_bound`, severity/fixed/CVE-алиасы, кэш `security_cache` 6 ч и stale-while-revalidate (S28-002).
- feat(security): regex Secret Scanner (AWS, GitHub token, JWT, private key) только по рабочей директории; маскирование, `# iiruchating:ignore-secret`, лимиты 5000 файлов / 1 MiB (S28-002).
- feat(api): `GET /api/v1/repositories/{id}/security` с `refresh`, `include_secrets`, `min_severity` (S28-003).
- feat(ui): блок «Безопасность» — severity-бейджи, CVE/OSV-ссылки, `fixed_version`, красный алерт о секретах с masked preview (S28-004).
- test(security): OSV-парсинг, CVSS, кэш/partial failure, secret-правила и маскирование, API-контракт (S28-005).
- feat(insights): `InsightsService` — churn hotspots за 3 месяца (`git log --name-only --no-merges`), топ-5 с фильтрацией lock/docs/generated/удалённых файлов (S29-001).
- feat(insights): DORA-lite commit frequency по дням с заполнением пустых дней и summary `commits/per_day/per_week` (S29-001).
- feat(insights): асинхронный `asyncio.create_subprocess_exec` runner, timeout 10 с, in-memory кэш 300 с, статусы `partial/no_branch/shallow_clone/timeout` (S29-001).
- feat(api): `GET /api/v1/repositories/{id}/insights` с `days` и `refresh` (S29-002).
- feat(ui): блоки «Технический долг (Hotspots)» и «Активность (30 дней)» — lazy `recharts` sparkline, счётчики churn и пустые состояния (S29-003).
- test(insights): парсинг git-log, фильтры, кэш, timeout/no_branch/shallow и реальный tmp-репозиторий (S29-004).
- feat(export): «Скопировать сводку» на дашборде — Markdown текущего среза (счётчики, проблемные проекты, mirror-статусы) + toast (S30-001).
- feat(workspace): экспорт/импорт UI-настроек в `iiruchating_workspace.json` — Saved Views, видимые колонки и ширины; валидация версии и лимит 1 MiB; токены/SCAN_ROOTS не экспортируются (S30-002).
- test(export): Markdown-форматирование/экранирование, workspace round-trip, отказ версии и импорт в Zustand-сторы (S30-001..S30-002).

### Документация

- docs(insights): SPEC §3.17 (фактические поля), ARCHITECTURE §13, CHANGELOG/RELEASES (S29-004).
- docs(security): SPEC §3.16 (фактические поля), ARCHITECTURE §12, ADR-0009, KI-011/012 в матрицу (S28-005).
- docs(planning): план v0.6.0 — supply-chain security (OSV.dev CVE, secret scanning), insights (hotspots, DORA-lite), collaboration/export; SPEC §3.16–3.17, ARCHITECTURE §12–14, KI-011/012 (S27-001..S27-003).
- docs(release): v0.6.0 — версии, README, RELEASES, итоговый docs-consistency audit (S30-003..S30-004).

## [0.5.0] - 2026-11-06

Наблюдаемость и управление зависимостями: тёмные графики M3, Docker-интеграция,
аудит Python- и Node-зависимостей.

### Добавлено

- feat(ui): M3-тема для recharts — оси, сетка, тултипы и легенды используют surface/on-surface, light/dark переключается без reload (S24-001).
- feat(docker): read-only Docker SDK интеграция — `GET /repositories/{id}/docker`, статусы `running/stopped/not_found/unavailable`, порты, health и compose-labels (S24-002).
- feat(docker): DooD — `/var/run/docker.sock:ro`, `DOCKER_HOST`, `DOCKER_PATH_MAP`; ошибки Docker не дают 5xx (S24-003).
- feat(ui): блок «Docker Containers» в деталях репозитория (S24-004).
- test(docker): fake Docker client, path mapping, cache/refresh и API-контракт.
- feat(deps): `dependency_cache` + миграция 006, TTL 24 ч, single-flight и stale-while-revalidate (S25-001).
- feat(deps): безопасный парсер `requirements.txt` — pins, ranges, extras, markers, `-r` include (S25-002).
- feat(deps): PyPI-клиент с timeout, retry/backoff на 429/5xx и partial results (S25-003).
- feat(deps): `GET /repositories/{id}/dependencies` с фильтром `ecosystem` (S25-004).
- feat(ui): блок «Зависимости» — счётчики, severity и ссылки на PyPI (S25-005).
- feat(deps): парсер `package.json` — `dependencies`/`devDependencies`, scoped/workspace/file/git (S26-001).
- feat(deps): npm registry client с timeout, retry/backoff и общим кэшем `npm:<name>` (S26-002).
- feat(deps): `ecosystem=all` и верхнеуровневый `summary` объединённого отчёта (S26-003).
- feat(ui): табы Python/Node и кнопка «Проверить всё» в блоке зависимостей (S26-003).
- test(deps): Node-парсер, npm-кэш, объединённый отчёт и API `ecosystem=all`.

### Документация

- docs(planning): план v0.5.0 — Dark Charts, Docker, зависимости Python/Node (S23-001..S23-003).
- docs(docker): SPEC §3.14, ARCHITECTURE §10, ADR-0007, KI-009.
- docs(deps): SPEC §3.15, ARCHITECTURE §11, ADR-0008, KI-010.

## [0.4.0] - 2026-11-05

UX/UI и продвинутый мониторинг: таблица, представления, палитра команд, A11y, конфликты, Telegram, heatmap и экспорт.

### Добавлено

- feat(a11y): иконки статусов (✓/↑/↓/⚠/!/✕), stale-индикатор 🕒 + opacity для данных старше 10 минут.
- feat(conflicts): `GET /repositories/{id}/conflicts` и блок Conflict Manager для `diverged`.
- feat(notify): Telegram Bot API (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`), logger fallback, `plyer` удалён (KI-007 Resolved).
- feat(activity): `GET /dashboard/heatmap` + contribution heatmap на дашборде.
- feat(export): `GET /repositories/export?format=csv|json` + кнопка «Экспорт» в UI.
- feat(keyboard): Command Palette (`Ctrl/Cmd+K`) — репозитории, страницы, scan/fetch/migrate.
- feat(keyboard): навигация по таблице `↑/↓`, `Enter`, `Space`, `/`, `Esc` + ring-подсветка.
- feat(keyboard): модалка горячих клавиш по `?` и подсказка в футере.
- feat(filters): filter chips (статус/зеркало/CI + untracked), OR внутри категории и AND между категориями.
- feat(views): сохранённые представления (фильтры, сортировка, колонки) в Zustand + localStorage.
- feat(url): синхронизация фильтров/поиска/сортировки с query string (`?status=…&mirror=…&q=…`).
- feat(dashboard): CI-агрегат в `GET /dashboard` (кэш 60 с) для CI-чипов и колонки.
- feat(table): batch selection (Zustand + persist), bulk fetch/sync по `repo_ids`, контекстное меню (open/fetch/copy path).
- feat(table): управление колонками (видимость/ширина, localStorage), моноширинные пути и SHA.

## [0.3.0] - 2026-11-05

Продуктивность и UI: массовые операции, тёмная тема, аналитика и настройки.

### Добавлено

- feat(settings): `app_settings` + `GET/PATCH /settings` с маскировкой токенов; значения подхватываются в конфиг при старте.
- feat(settings-ui): страница `/settings` (SCAN_ROOTS, токены, webhook secret, default provider) и ссылка в шапке.
- feat(migration): `POST /repositories/actions/migrate_to_gitflic` — массовый перевод canonical на GitFlic + отчёт.
- feat(ui): тёмная тема (`darkMode: 'class'`, ThemeProvider + localStorage, переключатель в шапке).
- feat(ui): аналитика дашборда — Pie Chart по состояниям и Bar Chart по `mirror_status` (recharts, lazy-загрузка).
- feat(ui): кликабельные строки таблицы, hover, поиск/сортировка, dark-варианты бейджей и модалок.
- feat(bulk): `POST /repositories/actions/fetch_all` и `/sync_mirrors_all` — фоновые массовые операции с `asyncio.Semaphore(5)`; sync пишет `action_log`.
- feat(cache): TTL-кэш провайдеров (`PROVIDER_CACHE_TTL_SECONDS=60`) для branch/list запросов GitHub/GitFlic.
- feat(ui): панель Fetch All / Sync Mirrors с polling каждые 2 с, поиск по имени/пути и сортировка таблицы.

## [0.2.0] - 2026-11-05

Наблюдаемость, зеркалирование GitHub ↔ GitFlic и безопасные мутации.

### Добавлено

- feat(ci): CI status GitHub Actions (`/repositories/{id}/ci-status`) + widget в UI; GitFlic — `not_supported`.
- feat(notify): desktop-уведомления (plyer) для `history_rewritten`/`missing_on_*`/`behind_gitflic` и `remote_status=unavailable` (rate-limit 1/час); настройки `NOTIFICATIONS_ENABLED`/`NOTIFY_ON`.
- feat(actions): явные мутации с `confirm=true` — `fetch`, `pull`, `push`, `stash`, `push_mirror`; аудит `action_log`, `GET /admin/actions`; UI-кнопка «Выполнить» с модалкой подтверждения.
- feat(mirror): межпровайдерное зеркало GitHub ↔ GitFlic — `repository_mirror_status`, `webhook_events`, миграция `003`.
- feat(mirror): клиенты GitHub/GitFlic (`get_branch`, `list_repos`, rate-limit → `unavailable`), `MirrorService` (9 статусов) и `MirrorScheduler` (polling 300 с).
- feat(mirror): API `GET/POST /repositories/{id}/mirror`, `PATCH /mirror-policy`, `GET /mirror/candidates`, webhooks с HMAC.
- feat(mirror): UI — вкладка «Зеркала», панель зеркала, настройка политики, копирование рекомендаций.
- feat(obs): Prometheus-метрики `/api/v1/metrics` — fetch/status histograms, `repositories_total{state}`, `scan_duration_seconds`.
- feat(obs): расширенный `/health` — `providers` (github/gitflic), `git_version` кэшируется при старте.
- feat(obs): structlog-события `fetch_failed` (с `remote_url`), `status_slow` (> 1 с), `scan_completed` с длительностью.

### Изменено

- fix(docker): каталог проектов монтируется как `C:/Projects:/projects`, `SCAN_ROOTS=/projects`; `git safe.directory` в образе.
- chore(ui): брендинг переименован в **ai-project-monitoring** (title, шапка, футер).
- perf: fast dirty check (KI-002) — `git status --porcelain -uno` перед `pygit2.status()`; чистый tracked-статус не грузит CPU.
- feat: compare cache (KI-003) — TTL-кэш `GET /repositories/{id}/compare` (60 с, инвалидация на refresh).
- fix: fetch timeout cleanup (KI-001) — таймаут fetch убивает процесс (`proc.kill()`), логирует подсказку увеличить `FETCH_TIMEOUT`.

## [0.1.0] - 2026-11-05

Первый MVP: сканирование, локальный статус, сравнение с удалённым, дашборд и рекомендации. Read-only.

### Добавлено

- **Discovery:** рекурсивный поиск `.git` в `SCAN_ROOTS` с `SCAN_DEPTH` и `SCAN_IGNORE` (case-insensitive, без входа в `.git`); запись истории в `scan_runs`; проверка глубины и вложенных репозиториев.
- **Data model:** SQLAlchemy 2.0 модели `Repository`, `RepositoryStatus`, `ScanRun`; Alembic-миграции `001` (таблицы) и `002` (поля git-статуса).
- **Git-абстракция:** `pygit2` для status/discovery/log/compare; shell `git` (subprocess, `asyncio.to_thread`) для `fetch --all --prune` и `rev-list`.
- **Канонический статус:** `current / behind / ahead / diverged / dirty / no_upstream / detached / error`; приоритет `detached → no_upstream → dirty → diverged → ahead → behind → current`; `ahead/behind` по локальным refs и после fetch.
- **Remote:** таймаут `FETCH_TIMEOUT`; ошибка/таймаут fetch → `remote_status=unavailable` без 500; успех → `ok`; без fetch → `stale`.
- **API (`/api/v1`):** `GET /health`, `POST /scan`, `GET /scan/{id}`, `GET /scan/latest`, `GET /repositories` (+ пагинация), `POST /repositories/{id}/track|untrack`, `GET /repositories/{id}/status|compare|log|recommendations`, `POST /repositories/{id}/refresh`, `GET /dashboard`.
- **Кэш статуса:** in-memory TTL + свежесть `checked_at` из БД (`STATUS_TTL_SECONDS=60`); `POST /refresh` обходит кэш.
- **Рекомендации:** `commit/stash`, `pull --rebase`, `push`, `pull`, `set-upstream` — только текст, без выполнения.
- **Frontend:** React 19 + Vite 8 + TypeScript, Tailwind; дашборд со сводкой и фильтрами «Все / Требуют внимания / Не отслеживаются», скан, таблица, track; страница деталей с коммитами и блоком «Рекомендации» (кнопка «Копировать»).
- **Бренд:** логотип, favicon, палитра M3 и шрифты Inter/Manrope.
- **Docker:** `backend/Dockerfile` (Python 3.12, libgit2, Alembic перед запуском), `frontend/Dockerfile` (Node 20 → nginx), `docker-compose.yml`, SPA-fallback и прокси `/api`.
- **Тесты:** 59 backend (реальные tmp-репозитории, bare-remote), 2 frontend (Vitest + Testing Library), read-only аудит кода.

### Ограничения

- Мутации (`pull`/`push`) не реализованы — только рекомендации (ADR-0003).
- Mirror GitHub ↔ GitFlic (`mirror_status`, polling, webhook) — v0.2.0.
- GitHub/GitFlic Compare API не используется; сравнение локальное (pygit2).
- История статусов не ведётся (только последний снимок).
- Покрытие кода в v0.1.0 не измерялось (`pytest-cov` не подключён).
