# RELEASES — Журнал спринтов

**Текущая версия:** v1.4.5 (2026-11-13)

---

## Хотфикс v1.4.5 — авторизация эмбеддингов и LLM_ALLOW_REMOTE в UI

**Дата:** 2026-11-13 · **Тег:** `v1.4.5`

RAG снова работает при включённой авторизации LM Studio, а разрешение
удалённых endpoint'ов настраивается без `.env`.

- **Авторизация:** `embed_or_raise()` формирует `Authorization: Bearer ...` из
  активного профиля (`api_key`), `EMBEDDING_API_KEY` или `LLM_API_KEY`;
  обёртка `embed()` использует тот же путь, `POST /settings/llm/test` — тоже.
- **Payload:** одиночный текст → строка, при HTTP 400 → массив; батчи — массив.
- **Логи:** `embedding_request` (полный payload, endpoint, модель, тип `input`,
  номер попытки), `embedding_request_headers` (`has_auth`, без токена),
  `embedding_request_failed` (+ `response_text`).
- **UI:** чекбокс «Разрешить удалённые подключения (LLM_ALLOW_REMOTE)» в блоке
  «AI Провайдеры»; сохраняется сразу через `PATCH /settings`, применяется к
  `config.LLM_ALLOW_REMOTE` и разрешает чат + эмбеддинги.
- **Проверки:** backend **365** (364 passed, 1 skipped), `ruff`, `mypy`;
  frontend **73** unit, `typecheck/lint/test/build`; sidecar пересобран.

---

## Хотфикс v1.4.4 — настройки RAG в UI и диагностика эмбеддингов

**Дата:** 2026-11-12 · **Тег:** `v1.4.4`

Настройки RAG больше не требуют редактирования `.env`, а ошибки LM Studio
видны в логах и в тесте LLM.

- **UI:** блок «Настройки RAG (Поиск по коду)» — `EMBEDDING_DIMENSIONS`
  (default 768), `RAG_CHUNK_SIZE` (1000), `RAG_CHUNK_OVERLAP` (150) с
  подсказками для nomic/OpenAI.
- **Backend:** новые ключи `app_settings` (`embedding_dimensions`,
  `rag_chunk_size`, `rag_chunk_overlap`) в `GET|PATCH /settings`; при старте
  применяются через `SettingsService.load_into_config()`. Legacy
  `RAG_CHUNK_CHARS` поддерживается как fallback.
- **Диагностика:** `LLMService` логирует `status_code` и `response_text`
  (≤ 2000 символов) для `>= 400`; `test_embedding` возвращает текст ответа.
- **Размерность:** перед индексацией — пробный `embed("test")`; при
  несовпадении `dimension_mismatch` с фактической/ожидаемой длиной.
  `POST /search/code/index` делает preflight и возвращает `503`.
- **Проверки:** backend **362** (361 passed, 1 skipped), `ruff`, `mypy`;
  frontend **73** unit, `typecheck/lint/test/build`; entry bundle **89.88 kB**
  gzip (budget 90 kB); sidecar пересобран.

---

## Спринт 63 — Global Tech Debt Dashboard

**Дата:** 2026-11-11 · **Тег:** `v1.4.3`

Глобальная картина технического долга по всем tracked-репозиториям и единый
формат отображения времени в UI.

- **Backend:** `GlobalStatsService` агрегирует outdated-пакеты, CVE по
  severity, dirty-файлы, diverged-ветки; считает детерминированный
  `problem_score` и топ-5 репозиториев. Агрегация идёт только по
  `tracked=true`, `asyncio.Semaphore(4)`, in-memory TTL-кэш **300 с** и
  single-flight; ошибка одного источника даёт `partial`/`error`, HTTP 200.
- **API:** `GET /api/v1/dashboard/global-stats` (`refresh`) и
  `POST /api/v1/dashboard/global-stats/ai-advice` (chat-модель, Markdown,
  `ai_cache`, `X-AI-Cache`, `503 llm_unavailable`).
- **UI:** lazy-блок «Tech Debt Overview» с карточками, Pie/Bar (`recharts`),
  топ-5 по `problem_score`, кнопкой «AI Анализ», partial/empty-состояниями,
  RU/EN и `aria`-описаниями.
- **UI polish:** `<RelativeTime />` — относительное время + кастомный тултип
  точной локальной даты (`Intl.DateTimeFormat`) вместо системного `title`;
  внедрён на дашборде и в деталях репозитория, поддержана тёмная тема.
- **Кэш:** первый запрос строит отчёт, второй отдаёт копию из памяти с
  `cached=true` и не вызывает источники; `refresh=true` обходит кэш.
- **Проверки:** backend **361** (360 passed, 1 skipped), `ruff`, `mypy`;
  frontend **73** unit, `typecheck/lint/test/build`; entry bundle **89.88 kB**
  gzip (budget 90 kB).

---

## Хотфикс v1.4.2 — разделение chat_model и embedding_model

**Дата:** 2026-11-11 · **Тег:** `v1.4.2`

Причина: LM Studio обслуживает чат и эмбеддинги разными моделями. До v1.4.2
RAG отправлял `model_name` (например, `qwen2.5-coder`) в `/v1/embeddings` и
падал с `embedding model is unavailable`.

- **Модель данных:** `ai_provider_profiles.embedding_model` (nullable),
  миграция `016`; backfill существующих OpenAI-совместимых профилей
  `text-embedding-nomic-embed-text-v1.5`.
- **LLMService:** чат-методы используют только `model_name`;
  `resolve_embedding()`/`embed_or_raise()` — только `embedding_model`.
  Пустое значение → `embedding_model_not_configured`, без подмены чат-моделью.
- **API/UI:** `embedding_model` в CRUD провайдера; второе поле в модалке;
  `/settings/llm/test` возвращает `chat` и `embedding` по отдельности.
- **RAG:** `embedding_model_unavailable: проверьте настройки AI-провайдера`
  при HTTP-ошибке; на `/search` — подсказка открыть «Настройки → AI Провайдеры».
- **Проверки:** backend **352** (351 passed, 1 skipped), `ruff`, `mypy`;
  frontend **67** unit, `typecheck/lint/test/build`; entry bundle **88.87 kB**
  gzip (budget 90 kB); sidecar собран, версия `1.4.2`.

---

## Хотфикс v1.4.1 — управление паролями

**Дата:** 2026-11-11 · **Тег:** `v1.4.1`

Итоги S61-004:

- **Смена своего пароля:** `PATCH /api/v1/users/me/password`, проверка старого
  пароля, bcrypt, аудит `password_changed`.
- **Админский сброс:** `POST /api/v1/users/{id}/reset-password` только для
  `admin`; аудитор получает `403 insufficient_role`, аудит `user_password_reset`.
- **UI:** раздел «Безопасность» в настройках (валидация и toast) и кнопка-ключ
  на странице «Команда» с модалкой и генератором пароля.
- **Проверки:** `test_passwords.py` (5 сценариев), полный backend pytest,
  `ruff`, `mypy`; frontend **66** unit (`AdminUsers.test.tsx`),
  `typecheck/lint/test/build`.

---

## Релиз v1.4.0 — «RAG on SQLite»

**Дата:** 2026-11-11 · **Тег:** `v1.4.0`

Итоги спринта 61:

- **S61-001 — sqlite-vec для desktop RAG:** `vec_chunks` (`vec0`,
  `distance_metric=cosine`) + `code_chunks` с JSON-эмбеддингами; KNN-поиск с
  фильтрами по проекту/языку; PostgreSQL/pgvector-путь без изменений.
  Если расширение не загрузилось — Python-косинус и лог
  `sqlite_vec_unavailable_fallback_to_python`.
- **S61-002 — упаковка:** `build_sidecar.py` кладёт `vec0.dll` в
  `PyInstaller`-бандл (`--add-binary`); frozen-бинарник проходит индексацию и
  поиск без `no such module: vec0`.
- **S61-003 — UX:** синий баннер и disabled-кнопки при `rag_unavailable`;
  «Открыть папку с логами» создаёт каталог, а при ошибке копирует путь в
  буфер с тостом «Путь скопирован».
- **Проверки:** backend **339** (338 passed, 1 skipped), `ruff`, `mypy`;
  frontend **65** unit, `typecheck/lint/test/build`; entry bundle **88.82 kB**
  gzip (budget 90 kB); frozen sidecar прошёл индексацию и поиск без
  `no such module: vec0`.
- **Зависимости:** `sqlite-vec==0.1.9`
  ([ADR-0022](adr/0022-sqlite-vec-desktop-rag.md)).

---

## Релиз v1.3.2 — «UX Polish & Smart Digest»

**Дата:** 2026-11-11 · **Тег:** `v1.3.2`

Итоги спринта 60 (по результатам ручного UX-тестирования v1.3.1):

- **S60-001 — умный AI-дайджест:** в промпт передаются конкретные списки
  (`repos_with_ahead`, `repos_with_most_outdated`, `critical_cves`,
  dirty/behind/diverged), LLM обязана назвать проекты в 3 рекомендациях.
- **S60-002 — локализация:** «Обновить всё», «Синхр. зеркала»,
  «Впереди / Позади», «Сборка».
- **S60-003 — тултипы:** bulk-кнопки, «Мигрировать на GitFlic» и кнопки шапки.
- **S60-004 — «Проверено»:** относительное время под статусом, точная дата в
  `title`; локальная утилита `formatRelativeTime`, новых зависимостей нет.
- **S60-005 — автодетект remote:** `parse_remote_url` понимает SSH/HTTPS и
  GitFlic-раскладку, `GET /repositories?detect_remote=true` отдаёт
  `detected_github_name` / `detected_gitflic_name`, модалка политики
  подставляет значения с подсказкой «Определено автоматически из git remote».
- **S60-Fix-001 — авто-хирургия БД:** база, где `alembic_version` уже 013/014,
  но в `users` нет `role`, чинится точечным `ALTER TABLE` + `UPDATE` и повторным
  `upgrade head`; данные не удаляются, событие `db_schema_repaired`.
- **S60-Fix-002 — версия на UI:** `GET /api/v1/health` → версия на экране входа
  и в шапке приложения.
- **S60-Fix-003 — сброс БД:** `POST /api/v1/auth/reset-db` (loopback +
  `confirm=true`) пересоздаёт SQLite и `admin/admin`; ссылка с подтверждением на
  экране входа.
- **Проверки:** backend pytest (все зелёные), `ruff`, `mypy`,
  frontend `typecheck/lint/test/build`, entry bundle 88.83 kB gzip
  (budget 90 kB).

---

## Хотфикс v1.3.1 — миграции БД в десктопном sidecar

**Дата:** 2026-11-11 · **Тег:** `v1.3.1`

Проблема: обновление v1.1.0 → v1.3.0 не применяло миграции — в базе
отсутствовала таблица `users`, bootstrap-админ не создавался, вход отвечал
«Неверный логин или пароль».

- Sidecar запускает Alembic программно (`alembic.command.upgrade(cfg, "head")`)
  до uvicorn; `alembic/` и `alembic.ini` упакованы в PyInstaller one-file.
- Базы без `alembic_version` распознаются по схеме, штампуются и догоняются
  до head, поэтому существующие таблицы не пересоздаются.
- Добавлен лог `bootstrap_admin_created`; путь данных совпадает с Tauri
  `app_data_dir`.
- Проверки: backend 325 (324 passed, 1 skipped), `ruff`, `mypy`.

---

## Релиз v1.3.0 — «.NET, Team Edition & SAST»

**Дата:** 2026-11-11 · **Тег:** `v1.3.0`

Итоги спринтов 57–59:

- **S57 — .NET Ecosystem Support:** парсер `.csproj`/`Directory.Packages.props`/
  `packages.config`, NuGet V3, CVE через OSV (`NuGet`), третья вкладка,
  `dotnet`-обновление, `.cs`/`.csproj` в hotspots/RAG.
- **S58 — Team Edition & Audit Log:** роли `admin`/`auditor`, `require_admin`,
  append-only `audit_log`, admin-страницы `/admin/users` и `/admin/audit`.
- **S59 — Advanced Security & Automated PRs:** `SastService` (bandit/semgrep/
  eslint fallback), кэш `sast_cache` 24 ч, блок SAST с AI-объяснением,
  генерация Dependabot/Renovate без записи и commit/push.
- **Проверки:** backend 321 (320 passed, 1 skipped), frontend 60 unit,
  `ruff`, `mypy`, `pnpm typecheck/lint/test/build`, entry bundle
  88.33 kB gzip (budget 90 kB).
- **Миграции:** 013 (roles/audit) и 014 (sast_cache).

---

## Спринт 59: Advanced Security & Automated PRs (v1.3.0)

**Дата:** 2026-11-11 · **Статус:** ✅ завершён

- [x] **S59-001. SAST:** `SastService`, bandit + semgrep + eslint fallback,
  нормализация severity, дедупликация, таймауты/лимиты, `sast_cache` 24 ч,
  `GET /api/v1/repositories/{id}/sast`, AI-объяснение находки.
- [x] **S59-002. Automated PRs:** `AutomationService` и
  `POST /automation/generate` для Dependabot/Renovate; только текст конфига,
  без записи, commit и push.
- [x] **S59-003. UI:** lazy-блок SAST и lazy-модалка «Автоматизация».
- [x] **S59-004. Release:** версии `1.3.0`, миграция 014, ADR-0020/0021,
  CHANGELOG/RELEASES/README/SPEC/ARCHITECTURE, тег `v1.3.0`.
- **Проверки:** backend 321 (320 passed, 1 skipped), frontend 60 unit,
  `ruff`/`mypy`, `pnpm build` и budget-check — ✅.

---

## Спринт 57: .NET Ecosystem Support (v1.3.0)

**Дата:** 2026-11-11 · **Статус:** ✅ завершён

- [x] **S57-001. .NET-парсер:** `.csproj`/`.fsproj`/`.vbproj`,
  `Directory.Packages.props` (CPM + `VersionOverride`), `packages.config`;
  `is_dev` для `PrivateAssets="all"`; безопасный XML без DTD/XXE; лимиты;
  неразрешимые MSBuild-свойства/conditions — `unknown` (KI-025).
- [x] **S57-002. NuGet и сервисы:** `NuGetClient` (flat container, stable
  SemVer, TTL-кэш 24 ч), `ecosystem="dotnet"` в `DependencyService`,
  OSV `ecosystem="NuGet"` в `SecurityService`, `is_dev` в схеме.
- [x] **S57-003. Обновление и инсайты:** `dotnet list package --outdated
  --no-restore` + `dotnet add <project> package <id> --no-restore` (только
  `confirm=true`, чистый worktree, `action_log`); `.cs`/`.fs`/`.csproj` в
  hotspots и RAG.
- [x] **S57-004. UI:** вкладка «C# / .NET», текущая/последняя версия, статус,
  ссылка на nuget.org, бейдж «Central Package Management».
- [x] **S57-005. Тесты и документация:** `test_dotnet_parser.py`, тесты
  зависимостей/обновлений/UI; SPEC §3.15/§3.15.1, ARCHITECTURE §29,
  CHANGELOG/RELEASES, ADR-0018.
- **Проверки:** backend 301 (300 passed, 1 skipped), frontend 59 unit,
  `ruff`, `mypy`, `pnpm typecheck/lint/test/build`, entry bundle
  87.93 kB gzip (budget 90 kB).
- **Ограничение:** MSBuild не вычисляется, приватные фиды и транзитивные
  зависимости вне scope; `dotnet` CLI нужен только для обновления пакетов.

---

## Спринт 58: Team Edition & Audit Log (v1.3.0)

**Дата:** 2026-11-11 · **Статус:** ✅ завершён

- [x] **S58-001. Роли:** `users.role` (`admin`/`auditor`, default `auditor`),
  миграция 013 сохраняет текущего admin; claim `role` в JWT;
  `require_admin` (`403 insufficient_role`) на actions, track/untrack,
  refresh, settings, AI-профилях, scan, RAG-индексации, users/audit.
- [x] **S58-002. Audit Log:** `AuditLog` + `AuditService`, append-only
  `audit_log`, логирование `scan_started`, `repo_push`/`repo_<action>`,
  `dep_update`, `settings_updated`, `user_created`/`role_changed`;
  `details` санитизируются (≤ 4000 символов). API `GET /api/v1/audit`,
  `GET/POST/PATCH /api/v1/users`.
- [x] **S58-003. UI:** lazy `/admin/users` (таблица, смена роли, приглашение с
  временным паролем) и `/admin/audit` (журнал, пагинация); ссылки в шапке
  только для admin.
- [x] **S58-004. Тесты и документация:** `test_auth_roles.py` (auditor `403`),
  `test_audit_log.py` (settings/roles, пагинация, санитизация), SPEC §3.31,
  ARCHITECTURE §31, CHANGELOG/RELEASES, ADR-0019.
- **Проверки:** backend 310 (309 passed, 1 skipped), frontend 59 unit,
  `ruff`, `mypy`, `pnpm typecheck/lint/test/build`, entry bundle
  88.28 kB gzip (budget 90 kB).
- **Ограничение:** роль проверяется на сервере на каждом запросе; retention
  audit log и гранулярные права на репозитории — кандидаты следующих версий.

---

## Релиз v1.2.0 — «AI Analytics & Cross-Platform»

**Дата:** 2026-11-09 · **Тег:** `v1.2.0`

Итоги спринтов 53–55:

- **S53 — Cross-Platform CI & AI Code Review:** матрица Windows/macOS/Linux,
  `.msi`/`.exe`/`.dmg`/`.AppImage`; AI-ревью незакоммиченных изменений с
  чанкингом и кэшем.
- **S54 — AI Conflict Resolver & Release Notes:** read-only объединение
  `<<<<<<<`-блоков, генерация Keep a Changelog между тегами, `GET /tags`.
- **S55 — Conversational RAG:** `/search/chat` — embedding запроса, top-5
  чанков из pgvector, ответ LLM только по контексту, цитаты на файлы;
  режим «Чат с кодом» на `/search`.
- **Проверки:** backend 276 (275 passed, 1 skipped), frontend 58 unit,
  `ruff`/`mypy`, `pnpm build` и budget-check.
- **Релиз:** тег `v1.2.0` запускает GitHub Actions для Windows/macOS/Linux.

---

## Спринт 54: AI Conflict Resolver & Release Notes (v1.2.0)

**Дата:** 2026-11-09 · **Статус:** ✅ Завершён

- [x] **S54-001. AI Conflict Resolver:** `POST /api/v1/repositories/{id}/ai/resolve-conflict`
  (`file_path`), безопасное чтение внутри репозитория, разбор маркеров,
  LLM-объединение, возврат полного файла **без записи**; кэш по блокам.
- [x] **S54-002. AI Release Notes:** `POST /api/v1/repositories/{id}/ai/release-notes`
  (`from_tag`, `to_tag`), `git log --oneline`, Keep a Changelog, кэш;
  `GET /repositories/{id}/tags` для выбора тегов.
- [x] **S54-003. UI и документация:** кнопки «AI Подсказка» и «AI Release Notes»,
  lazy-модалки с Markdown/копированием; SPEC §3.29, CHANGELOG/RELEASES/README,
  KI-023.
- **Проверки:** backend 273 (272 passed, 1 skipped), frontend 57 unit,
  `ruff`/`mypy`, `pnpm build` и budget-check — см. отчёт спринта.

---

## Спринт 53: Cross-Platform CI & AI Code Review (v1.2.0)

**Дата:** 2026-11-09 · **Статус:** ✅ Завершён

- [x] **S53-001. Cross-Platform CI:** матрица `windows-latest` / `macos-latest` /
  `ubuntu-latest`; Windows `.msi`/`.exe`, macOS `.dmg`, Linux `.AppImage`;
  Linux-зависимости (`libwebkit2gtk-4.1-dev`, `libayatana-appindicator3-dev`,
  `librsvg2-dev`, `patchelf`, `libxdo-dev`), macOS `pkg-config`; sidecar
  собирается под target triple каждой ОС.
- [x] **S53-002. AI Code Review:** `POST /api/v1/repositories/{id}/ai/code-review`,
  `LLMService.review_code()`, чанкинг diff >5000 символов, map-reduce, кэш
  `ai_cache` по хэшу diff, fallback `git diff --cached`.
- [x] **S53-003. UI:** кнопка «AI Code Review» рядом с «Сгенерировать коммит»,
  lazy-модалка `CodeReviewModal` с Markdown, спиннером и копированием.
- [x] **S53-004. Документация:** SPEC §3.29, CHANGELOG, RELEASES,
  GETTING_STARTED, README.
- **Проверки:** backend 267 (266 passed, 1 skipped), frontend 55 unit,
  `ruff`/`mypy`, `pnpm build` и budget-check — см. отчёт спринта.

---

## Релиз v1.1.0 — «Seamless Updates & Onboarding»

**Дата:** 2026-11-09 · **Тег:** `v1.1.0`

Итоги спринтов 50–51:

- **S50 — Onboarding & Logging:** `GET /api/v1/settings/status`, мастер первичной
  настройки `/onboarding` (папки сканирования, опциональные GitHub/GitFlic
  токены, первый scan), автопереход на wizard при `is_configured=false`;
  файловые логи Tauri в `%APPDATA%/IIRuchating/logs/app.log` с ротацией 5 МБ и
  кнопкой «Открыть папку с логами».
- **S51 — Auto-Updates & CI/CD:** Tauri Updater с подписанными артефактами и
  endpoint `releases/latest/download/latest.json`; раздел «Обновления» в
  настройках (проверка, прогресс, установка, перезапуск); GitHub Actions
  `release-desktop.yml` собирает Windows `.msi`/`.exe` и публикует Release по
  тегу `v*`.
- **Проверки:** backend 259 (258 passed, 1 skipped), frontend 53 unit + 3 E2E,
  entry bundle 87.80 kB gzip.
- **Обновление:** установленные v1.0.0+ клиенты получают v1.1.0 автоматически
  через «Настройки → Обновления».

---

## Релиз v1.0.0 — «Secure Desktop»

**Дата:** 2026-11-08 · **Тег:** `v1.0.0`

Итоги спринтов 45–49:

- **S45 — PostgreSQL & RAG:** Docker Compose с `pgvector/pgvector:pg16`,
  `code_chunks`, индексация и поиск; SQLite fallback `503 rag_unavailable`.
- **S46 — Planning:** roadmap v1.0.0, контракты auth/Tauri, KI-019/KI-020.
- **S47 — Single-User Auth:** bcrypt, JWT (7 дней), httpOnly cookie, middleware,
  login/me/logout, rate-limit, protected routes.
- **S48 — Tauri Desktop:** PyInstaller sidecar, SQLite в AppData, health poll,
  graceful shutdown, Windows `.msi` + NSIS `.exe`.
- **S49 — Release:** аудит безопасности, KI-021/KI-022, версии 1.0.0,
  финальные артефакты и GitHub Release.
- **Проверки:** backend 254 (253 passed, 1 skipped), frontend 45 unit + 3 E2E,
  entry bundle 89.62 kB gzip.
- **Ограничения:** неподписанные Windows-инсталляторы (KI-021); RAG в desktop
  требует внешнего PostgreSQL (KI-022).

---

## Спринт 48: Tauri Desktop App (v1.0.0)

**Дата:** 2026-11-08 · **Статус:** ✅ Завершён (Windows)

- [x] PyInstaller sidecar: `backend/build_sidecar.py`, `--onefile --noconsole`, pygit2/bcrypt/aiosqlite, `--port`/`--data-dir`.
- [x] `TAURI_MODE=true` → SQLite в `%APPDATA%/IIRuchating`; health endpoint проверен standalone.
- [x] Tauri 2 shell: spawn sidecar, свободный порт, `backend_url`, process group/job object, `RunEvent::Exit` kill.
- [x] Frontend: splash + `/health` poll перед монтированием React; Bearer fallback для desktop.
- [x] Windows `.msi` (26.85 MiB) и NSIS `.exe` (25.74 MiB) собраны; закрытие приложения не оставляет backend.
- [x] ADR-0017, README, ARCHITECTURE §25, TODO_V1.0.
- **Проверки:** backend 254 (253 passed, 1 skipped), frontend 45 unit + 3 E2E, entry bundle 89.62 kB gzip.

---

## Спринт 47: Single-User Authentication (v1.0.0)

**Дата:** 2026-11-08 · **Статус:** ✅ Завершён

- [x] Модель `User` и миграция `012_users`; bcrypt (cost 12).
- [x] `AuthService`: JWT HS256 (7 дней), bootstrap `admin/admin`, rate-limit 5/60.
- [x] API `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`; httpOnly cookie `iiruchating_session` + Bearer.
- [x] `AuthMiddleware`: все `/api/v1/*`, кроме `/health`, `/metrics`, `/auth/login`.
- [x] Frontend: lazy `/login`, `useAuthStore`, protected routes, logout в шапке, RU/EN.
- [x] Тесты: backend auth/rate-limit/cookie/Bearer; frontend Login; E2E-моки auth.
- **Проверки:** `pytest` (254 collected: 253 passed, 1 skipped), `ruff`, `mypy`, 45 unit, 3 E2E, entry bundle 89.32 kB gzip.

---

## Релиз v0.9.0 — «Stability & RAG»

**Дата:** 2026-11-08 · **Тег:** `v0.9.0`

Итоги спринтов 41–44:

- **S41 — Planning:** план v0.9.0, контракты RAG/GigaChat/Smart Cache.
- **S42 — E2E & Bundle:** Playwright-сценарии (onboarding, RU/EN + тема,
  AI-коммит) на моках; entry bundle 99.0 → **89.99 kB gzip**; lazy i18n-словари;
  budget-check.
- **S43 — GigaChat & Smart Cache:** аудит `.env` → UI, сид `app_settings`,
  GigaChat OAuth 2.0 с refresh, state-hash кэш LLM с `X-AI-Cache`, метрики.
- **S44 — RAG & Release:** `CodeSearchService` на PostgreSQL + pgvector,
  индексация README/docs/src, семантический поиск, lazy-страница `/search`,
  релиз v0.9.0.
- **Проверки:** backend `pytest` (246 тестов), `ruff`, `mypy`; frontend 44 unit
  + 3 E2E; bundle budget зелёный.
- **Ограничение:** RAG доступен только на PostgreSQL + pgvector; на SQLite
  API отвечает `503 rag_unavailable` (KI-017).

---

## Релиз v0.8.0 — «AI Workspace»

**Дата:** 2026-11-08 · **Тег:** `v0.8.0`

Итоги этапа (спринты 35–40):

- **Data Correctness (S35):** вложенные манифесты зависимостей, README/docs viewer,
  рекомендации наверху и всегда свежие, `arhiv-del` в tracked.
- **RU/EN & Dashboard UX (S36):** собственный i18n, переключатель языка,
  кликабельные сводки, сворачиваемые разделы, человеческие подписи.
- **Remote Identity & AI Unification (S37):** группировка дублей по remote URL,
  AI-советы по унификации, блок «Унификация» в карточке проекта.
- **AI Recommendations & DSH Tasks (S38):** AI-дайджест дашборда, задачи для
  DSH/OpenCode, проверка LLM.
- **AI Provider Profiles (S39):** профили OpenAI-совместимых провайдеров,
  активация без перезапуска, маскировка ключей.
- **Release (S40):** аудит документации, версии `0.8.0`, тег и GitHub Release.
- **Метрики:** 228 backend + 44 frontend тестов; entry bundle 99.0 kB gzip
  (lazy: AI-дайджест, задача агента, профиль AI).

---

## Спринт 43: Settings Audit, GigaChat & Smart Cache (v0.9.0)

**Дата:** 2026-11-08 · **Статус:** ✅ Завершён

### Сделано

- [x] S43-001: аудит `.env` → UI: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `NOTIFICATIONS_ENABLED`, `FETCH_TIMEOUT`, `STATUS_TTL_SECONDS`, `MIRROR_POLL_INTERVAL_SECONDS`; группы «Уведомления»/«Производительность»; сид `app_settings` из `config.py` при пустой БД; runtime-применение без перезапуска.
- [x] S43-002: `provider_type`/`auth_type` в `ai_provider_profiles` (миграция `010`), `GigaChatProvider` с OAuth 2.0, in-memory token cache, refresh margin, single-flight, повтор после `401`; API `gigachat/auth` и `gigachat/refresh`; UI-модалка и статус токена.
- [x] S43-003: `AICacheKeyBuilder` (`state_hash` + `prompt_version`), smart-кэш для dashboard-advice, unification-advice, CVE и commit message; `X-AI-Cache`, `refresh=true`, single-flight, метрики `ai_cache_hits/misses`, `ai_llm_calls`.
- [x] S43-004: `test_gigachat.py`, `test_smart_cache.py`, тесты сида/новых настроек; ADR-0012, SPEC §3.12/§3.25/§3.27, CHANGELOG/RELEASES.
- **Проверки:** backend `pytest`/`ruff`/`mypy` — 0; frontend 44 unit + 3 E2E; entry bundle 89.85 kB gzip.

---

## Спринт 39: AI Provider Profiles (v0.8.0)

**Дата:** 2026-11-08 · **Статус:** ✅ Завершён

### Задачи

- [x] S39-001: модель `AIProviderProfile`, таблица `ai_provider_profiles`, миграция `009` с переносом текущих `llm_*` в профиль по умолчанию.
- [x] S39-001 API: `GET/POST/PATCH/DELETE /settings/ai-providers`, `POST .../{id}/activate`; ключи маскируются.
- [x] S39-002: `LLMService.resolve()` читает активный профиль из БД при каждом вызове, fallback на `config.py`; смена без перезапуска.
- [x] S39-003 UI: список карточек провайдеров, активация/редактирование/удаление, lazy-модалка, пустой API key сохраняет старый.
- [x] S39-004: `test_ai_providers.py` (CRUD, маскировка, активация, переключение LLMService), SPEC §3.25, ARCHITECTURE §15.7.

### Результаты

- Backend-тесты: 228 passed.
- Frontend-тесты: 44 passed.
- Entry bundle: **98.99 kB gzip** (< 100 kB). Модалка профиля — lazy-чанк **1.19 kB**.
- Активный профиль применяется без перезапуска приложения.

---

## Спринт 38: AI Recommendations & DSH Tasks (v0.8.0)

**Дата:** 2026-11-08 · **Статус:** ✅ Завершён

### Задачи

- [x] S38-001: `POST /ai/dashboard-advice` — агрегаты state/dirty/diverged/outdated/CVE, 2–3 рекомендации LLM, кэш `ai_cache` 1 час.
- [x] S38-001 UI: lazy-виджет «AI Дайджест» с кнопкой «Сгенерировать» и Markdown.
- [x] S38-002: `POST /repositories/{id}/ai/agent-task` — Markdown-задача для DSH/OpenCode по state, dirty, конфликтам и последним коммитам.
- [x] S38-003 UI: кнопка «Создать задачу для агента» и lazy-модалка с копированием.
- [x] S38-003: `POST /settings/llm/test` (ping, latency/error) и кнопка «Проверить LLM».
- [x] S38-004: backend-тесты advice/agent task/LLM test, UI-тест дайджеста, SPEC §3.24, ARCHITECTURE §15.5.

### Результаты

- Backend-тесты: 225 passed (добавлено 5).
- Frontend-тесты: 44 passed.
- Entry bundle: **98.43 kB gzip** (< 100 kB). Новые тяжёлые части вынесены в lazy-чанки:
  `AiDigest` 0.83 kB, `AgentTaskModal` 1.13 kB, общий `MarkdownView` 1.74 kB.
- AI-дайджест и модалка задачи не попадают в основной бандл.

---

## Спринт 37: Remote Identity & AI Unification (v0.8.0)

**Дата:** 2026-11-08 · **Статус:** ✅ Завершён

### Задачи

- [x] S37-001: `IdentityService` — чтение `remote.origin.url`, нормализация https/ssh/scp, группировка одинаковых remote; `GET /dashboard/duplicates`.
- [x] S37-002: `LLMService.advise_unification` и `POST /dashboard/global-dependencies/ai-advice`; кэш `ai_cache` 7 дней; 400/404/503-контракты.
- [x] S37-002 UI: кнопка «AI Совет»/«AI advice» с поповером и признаком кэша.
- [x] S37-003: блок «Унификация» в карточке проекта с версией у вас/в других проектах и кнопкой «Обновить до X».
- [x] S37-004: `test_duplicates.py`, `test_ai_unification.py`, frontend-тест AI-совета; SPEC §3.22–3.23, ARCHITECTURE §16.4/§19.

### Результаты

- Дубликаты группируются по нормализованному remote, а не только по имени каталога.
- AI-совет отправляет только имя пакета и распределение версий/проектов; код и diff не уходят.
- Backend-тесты: 220 passed (добавлено 6 тестов), frontend — 43.
- Entry bundle 98.0 kB gzip (лимит 100 kB); новые UI-элементы в существующих lazy-сегментах.

---

## Спринт 36: RU/EN i18n & Dashboard Interaction (v0.8.0)

**Дата:** 2026-11-08 · **Статус:** ✅ Завершён

### Задачи

- [x] S36-001: фильтры и аналитика сворачиваются; дашборд всегда виден.
- [x] S36-002: все пять карточек сводки кликабельны и ведут в отфильтрованный список.
- [x] S36-003: группа «Репозитории», человеческие подписи статусов/зеркал в фильтрах, таблице и графиках.
- [x] S36-004: собственный i18n без зависимостей — RU/EN, `localStorage`, `Intl`, `document.lang`; переключатель рядом с темой.
- [x] S36-005 (частично): tooltips/aria для новых контролов и опасных действий.
- [x] Переведены все видимые строки: шапка, дашборд, настройки, карточка репозитория, README-модалка, команды и горячие клавиши.

### Результаты

- RU/EN переключается без перезагрузки; выбор сохраняется.
- Статусы в UI: «чистый», «отстаёт», «впереди», «есть изменения», «расходится», «нет upstream», «не отслеживается».
- Попутный fix: commit frequency в Insights использует локальную дату (устранено выпадение коммитов после локальной полуночи, найденное при полном прогоне).
- Графики используют те же подписи; легенда зеркал без технического `value`.
- Frontend-тесты: 43 passed (добавлен тест переключения языка и сохранения выбора).
- Read-only: i18n не меняет данные и репозитории.

---

## Спринт 35: Data Correctness & Repository Context (v0.8.0)

**Дата:** 2026-11-07 · **Статус:** ✅ Завершён

### Задачи

- [x] S35-001: `ManifestDiscovery` — вложенные `requirements.txt`/`package.json` до depth 3, ignore-лист, `DEPENDENCY_MANIFEST_MAX_DEPTH`; DependencyService и SecurityService используют общий слой; `manifests[]`, `manifest_path`, дедупликация пакетов.
- [x] S35-002: `ReadmeService` и endpoints `/readme`, `/docs`; парсинг H1/версии, лимит 512 KiB, запрет traversal и `.git`; UI «визитка» + модалка с внутренними ссылками и «Назад».
- [x] S35-003: блок «Рекомендации» перенесён наверх; после действия статус обновляется до пересчёта рекомендаций (устранена гонка `Promise.all`).
- [x] S35-004: `arhiv-del` возвращён в tracked; объяснение ручного untrack.
- [x] Частично S36-001..S36-003: сворачиваемые фильтры, скрытая аналитика, кликабельные карточки сводки, группа «Репозитории», человеческие подписи статусов/зеркал в фильтрах и графиках.

### Результаты

- Python-зависимости проекта теперь видны из `backend/requirements.txt` (16 пакетов), Node — из `frontend/package.json` (20 пакетов).
- Security-сканер использует те же вложенные манифесты (16 Python + 20 Node пакетов проверены OSV).
- README открывается в модалке; `docs/SPEC.md` и другие внутренние ссылки работают с историей навигации.
- Backend-тесты: добавлены `test_readme.py` (6) и тесты вложенных манифестов; frontend — 42 теста.
- Read-only: README/docs только читаются; рекомендации и статус не мутируют репозиторий.

---

## Релиз v0.7.0 — «AI-Powered Assistant»

**Дата:** 2026-11-06 · **Тег:** `v0.7.0`

Итоги этапа (спринты 31–34):

- **Planning (S31):** контракты v0.7.0, KI-013/014.
- **LLM & AI Commit Messages (S32):** локальный OpenAI-совместимый клиент,
  настройки LLM, генерация Conventional Commits по diff, действие `commit`.
- **AI Security & Global Dashboard (S33):** объяснение CVE с кэшем `ai_cache`,
  глобальная агрегация версий и бейдж «Унифицировать».
- **Automated Dependencies & Release (S34):** явное обновление пакетов с
  preflight по чистому worktree, аудитом и UI-подтверждением.
- **Итоговые тесты:** 206 backend + 38 frontend; entry bundle 85.61 kB gzip.

---

## Спринт 34: Automated Dependencies & Release v0.7.0

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S34-001: `DependencyUpdateService` — pip/pnpm/npm, preflight `git status --porcelain`, timeout 180 с, output cap 10000 символов, redaction credentials.
- [x] S34-002: `POST /repositories/{id}/actions/update-dependencies` и bulk `202`; `400 confirmation_required`, `409 "Worktree must be clean"`/`no_manifest`, `action_log` для успеха/ошибки/отказа.
- [x] S34-003: кнопка «Обновить пакеты» (disabled на dirty), модалка подтверждения, toast и refresh статуса/зависимостей.
- [x] S34-004: `test_dependency_updates.py` (8 тестов), UI-тесты, ADR-0011.
- [x] S34-005: версии `0.7.0`, CHANGELOG/RELEASES/README/SPEC, тег и GitHub Release.

### Результаты

- Backend-тесты: 206 passed
- Frontend-тесты: 38 passed
- Entry bundle: 85.61 kB gzip; `RepositoryDetails` — 11.12 kB, `Dashboard` (с Global Dependencies) — 8.92 kB.
- Read-only: обновление только по `confirm=true` и на чистом worktree; автоматического коммита нет.

---

## Спринт 33: AI Security Insights & Global Dashboard (v0.7.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S33-001: `GlobalAnalyticsService` — агрегация `DependencyService` по tracked-репозиториям, `distribution`, `latest_version`, `unification_needed`, кэш 1 час.
- [x] S33-002: `LLMService.explain_cve(cve_id, summary)` и `POST /repositories/{id}/ai/cve-explain`; `ai_cache` на 7 дней.
- [x] S33-003: `GET /api/v1/dashboard/global-dependencies` (`refresh`); ответ `{ecosystems: {python, node}}`.
- [x] S33-004: блок «Global Dependencies» на дашборде (бейдж «Унифицировать») и CVE-модалка «Объяснить» в деталях.
- [x] S33-005: `test_global_analytics.py` (6 тестов), `test_ai_explain.py` (7 тестов), SPEC §3.18.2/§3.19, ARCHITECTURE §15.4/§16.

### Результаты

- Backend-тесты: 198 passed
- Frontend-тесты: 36 passed
- Read-only: CVE explain/global analytics не меняют репозиторий.
- `ai_cache` хранит только текст объяснения; LLM-ошибка → `503`, без fallback-текста.

---

## Спринт 32: LLM Provider & AI Commit Messages (v0.7.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S32-001: `LLMService` — OpenAI-совместимый `POST /v1/chat/completions` (LM Studio/Ollama), timeout 30 с, remote-guard, очистка ответа; ошибки → `None`.
- [x] S32-002: settings `llm_enabled/base_url/model/api_key/timeout/max_diff_chars/allow_remote`, маскировка ключа, секция «AI / LLM» в UI.
- [x] S32-003: `git diff HEAD` + лимит 10000 символов с `[diff truncated]`, `CommitMessageSuggestion`.
- [x] S32-004: `POST /repositories/{id}/ai/commit-message`; `commit` в `ActionService` с `confirm=true`, сообщением и `action_log`.
- [x] S32-005: кнопка «Сгенерировать коммит», модалка с лоадером/textarea/копированием и подтверждённым коммитом, toast при ошибке LLM.
- [x] S32-006: `test_llm.py` (13 тестов), SPEC §3.18.1, ARCHITECTURE §15, ADR-0010, CHANGELOG/RELEASES.

### Результаты

- Backend-тесты: 188 passed
- Frontend-тесты: 34 passed
- Read-only: AI-эндпоинт не коммитит; `commit` — отдельное действие с подтверждением.
- Diff/промпты не логируются; `llm_api_key` маскируется.

---

## Релиз v0.6.0 — «Security & Insights»

**Дата:** 2026-11-06 · **Тег:** `v0.6.0`

Итоги этапа (спринты 27–30):

- **Planning (S27):** контракты и план v0.6.0, KI-011/012.
- **Supply Chain Security (S28):** CVE через OSV.dev, regex Secret Scanner, блок
  «Безопасность», `security_cache` 6 ч.
- **Tech Debt & Insights (S29):** hotspots по churn, DORA-lite commit frequency
  со sparkline, кэш 300 с и безопасный subprocess-runner.
- **Collaboration & Release (S30):** Markdown-сводка, Workspace export/import,
  версии 0.6.0, итоговый аудит и тег.
- **Итоговые тесты:** 175 backend + 32 frontend; entry bundle 85.62 kB gzip;
  `InsightsSparkline` — 6.55 kB gzip (lazy).

---

## Спринт 30: Collaboration & Release v0.6.0

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S30-001: кнопка «Скопировать сводку» на дашборде — Markdown текущего среза (summary, проблемные проекты, mirror-статусы) + toast.
- [x] S30-002: `getExportState`/`importState` в `useViewsStore` и `useTableStore`; экспорт/импорт `iiruchating_workspace.json` на странице настроек с валидацией версии и лимитом 1 MiB.
- [x] S30-003: версии `0.6.0` (backend/frontend), CHANGELOG `[0.6.0]`, RELEASES, README, SPEC §3.16–3.17 и §9.11.
- [x] S30-004: финальные проверки, тег `v0.6.0` в GitHub/GitFlic, GitHub Release.

### Результаты

- Backend-тесты: 175 passed
- Frontend-тесты: 32 passed
- Entry bundle: 85.62 kB gzip; `RepositoryDetails` — 9.37 kB, `InsightsSparkline` — 6.55 kB (lazy).
- Workspace export не содержит токенов и `SCAN_ROOTS`; импорт отклоняет чужую версию схемы.

---

## Спринт 29: Tech Debt & Insights (v0.6.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S29-001: `InsightsService` — churn hotspots (`git log --no-merges --name-only --since="3 months ago"`), топ-5, фильтры lock/docs/generated/удалённых файлов.
- [x] S29-001: DORA-lite commit frequency (`git log <branch> --format=%ad --date=short`) с заполнением пустых дней и summary `commits/per_day/per_week`.
- [x] S29-001: `asyncio.create_subprocess_exec` runner, `GIT_OPTIONAL_LOCKS=0`, timeout 10 с, лимит stdout 8 MiB, in-memory кэш 300 с.
- [x] S29-002: `GET /api/v1/repositories/{id}/insights` (`days`, `refresh`).
- [x] S29-003: UI — блоки «Технический долг (Hotspots)» и «Активность (30 дней)» с lazy `recharts` sparkline.
- [x] S29-004: тесты (`test_insights.py`), SPEC §3.17, ARCHITECTURE §13, CHANGELOG/RELEASES.

### Результаты

- Backend-тесты: 175 passed
- Frontend-тесты: 23 passed
- Entry bundle: 85.59 kB gzip; `InsightsSparkline` — 6.55 kB gzip (lazy), `RepositoryDetails` — 9.37 kB gzip.

---

## Спринт 28: Supply Chain Security (v0.6.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S28-001: `OsvClient` — `POST /v1/querybatch` (PyPI/npm), батчи по 100, retry/backoff, CVSS v3 base score из вектора.
- [x] S28-002: `SecurityService` — CVE для Python/Node-манифестов, `exact`/`lower_bound`/`unknown`, severity mapping, `security_cache` (TTL 6 ч) и stale-while-revalidate.
- [x] S28-002: базовый Secret Scanner — AWS Access Key/Secret, GitHub token, JWT, private key; только рабочая директория, маскирование, ignore-маркер, лимиты файлов/размера.
- [x] S28-003: `GET /api/v1/repositories/{id}/security` (`refresh`, `include_secrets`, `min_severity`).
- [x] S28-004: UI-блок «Безопасность» в деталях репозитория — severity-бейджи, CVE/OSV-ссылки, красный алерт о секретах.
- [x] S28-005: тесты (`test_security.py`), ADR-0009, SPEC §3.16, ARCHITECTURE §12, CHANGELOG.

### Результаты

- Backend-тесты: 164 passed
- Frontend-тесты: 20 passed
- Read-only: `pip`/`npm` не запускаются, история Git не сканируется; секреты только в masked preview.

---

## Релиз v0.5.0 — «Observability & Dependency Management»

**Дата:** 2026-11-06 · **Тег:** `v0.5.0`

Итоги этапа (спринты 24–26):

- **Dark Charts (S24):** M3-палитра recharts для light/dark, токены осей,
  сетки, тултипов и легенд.
- **Docker Integration (S24):** read-only Docker SDK, DooD через socket,
  статусы контейнеров, порты и `DOCKER_PATH_MAP`.
- **Dependency Management (S25):** парсер `requirements.txt`, PyPI-клиент,
  `dependency_cache` 24 ч, UI-блок и API.
- **Dependency Management (S26):** парсер `package.json`, npm-клиент,
  `ecosystem=all`, объединённый `summary`, табы Python/Node в UI.
- **Релиз (S26):** версии 0.5.0, docs-consistency audit, тег в GitHub и GitFlic.

**Итоговые метрики:** 148 backend-тестов, 17 frontend-тестов;
entry bundle 85.59 kB gzip, `RepositoryDetails` — 7.09 kB,
`DashboardCharts` — 114.55 kB gzip (lazy).

**Release smoke:** `/health` → `version=0.5.0`; `ecosystem=node` для
`ai-dzenwriter` → 9 пакетов, 2 outdated; `ecosystem=all` → `summary`
9/2 (Python no_manifest + Node); Docker-контейнеры проекта — `running`.

---

## Спринт 24: Dark Charts & Docker Integration (v0.5.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S24-001: M3-тема для recharts — оси, сетка, тултипы и легенды используют
  `surface`/`on-surface`, light/dark переключается без перезагрузки.
- [x] S24-002: `DockerService` на Python Docker SDK — read-only `ping` +
  `containers.list(all=True)`, `DockerStatus` (`running/stopped/not_found/unavailable`),
  кэш 30 с, `DOCKER_PATH_MAP`.
- [x] S24-003: DooD — `/var/run/docker.sock:ro`, `DOCKER_HOST`, конфигурация
  `PROJECTS_ROOT`; ошибки Docker не дают 5xx.
- [x] S24-004: UI-блок «Docker Containers» с бейджами, портами и ошибками;
  типы `DockerStatus` во frontend.
- [x] Тесты, SPEC §3.14, ARCHITECTURE §10, ADR-0007, CHANGELOG, KI-009.

### Метрики

- Backend: **131 passed** (включая 10 Docker-тестов на fake SDK).
- Frontend: **14 passed**; entry bundle **85.59 kB gzip**, `RepositoryDetails`
  — 5.45 kB, `DashboardCharts` — 114.55 kB gzip (lazy).
- Docker smoke: `GET /repositories/26/docker` → `running`, backend/frontend
  контейнеры, порты 8000/3000; `GET /repositories/1/docker` → `not_found`
  (у репозитория нет контейнеров).

---

## Спринт 25: Dependency Management (Python) (v0.5.0)

**Дата:** 2026-11-06 · **Статус:** ✅ Завершён

### Задачи

- [x] S25-001: `dependency_cache` + миграция `006`, TTL 24 ч, single-flight,
  stale-while-revalidate.
- [x] S25-002: безопасный парсер `requirements.txt` (`-r` include, cycles,
  path traversal, pins/ranges/extras/markers).
- [x] S25-003: PyPI-клиент с timeout, retry/backoff на 429/5xx и partial results.
- [x] S25-004: `GET /repositories/{id}/dependencies` с `refresh` и `ecosystem`.
- [x] S25-005: UI-блок «Зависимости» со счётчиками, severity и ссылками на PyPI.
- [x] S25-006: тесты парсера, кэша, single-flight, stale, API и UI.
- [x] S25-007: ADR-0008, SPEC §3.15, ARCHITECTURE §11, KI-010, CHANGELOG.

### Метрики

- Backend: **145 passed** (включая 14 dependency-тестов).
- Frontend: **16 passed**; entry bundle **85.59 kB gzip**,
  `RepositoryDetails` — 6.82 kB, `DashboardCharts` — 114.55 kB gzip (lazy).
- Smoke: временный root `requirements.txt` (fastapi==0.115.6, requests>=2.31)
  → `GET /repositories/26/dependencies?ecosystem=python&refresh=true` вернул
  `status=ok`, `source=registry`, 2 outdated; повторный запрос — `source=cache`.
  Файл после проверки удалён.

---

## Релиз v0.4.0 — «UX & Advanced Monitoring»

**Дата:** 2026-11-05 · **Тег:** `v0.4.0`

Итоги этапа (спринты 17–22):

- **Advanced Data Table (S18):** batch selection, bulk по выбранным, контекстное меню, управление колонками.
- **Filtering & Saved Views (S19):** filter chips, сохранённые представления, URL-состояние, CI-агрегат в dashboard.
- **Keyboard (S20):** Command Palette (`Ctrl/Cmd+K`), навигация по таблице, панель подсказок `?`.
- **Visuals/A11y (S21):** иконки статусов, stale-индикатор, Conflict Manager, contribution heatmap, экспорт CSV/JSON.
- **Notifications (S21):** Telegram Bot API вместо `plyer`; KI-007 и KI-008 закрыты.
- **Релиз (S22):** docs-consistency audit, тег `v0.4.0` в GitHub и GitFlic.

**Итоговые метрики:** 121 backend-тест, 11 frontend-тестов, entry ~86 kB gzip
(графики и Command Palette — отдельные lazy-chunks).

---

## Релиз v0.3.0 — «Productivity & UI»

**Дата:** 2026-11-05 · **Тег:** `v0.3.0`

Итоги этапа (спринты 13–16):

- **Bulk Actions (S13):** массовые `fetch_all`/`sync_mirrors_all` с `asyncio.Semaphore(5)` и фоновыми API.
- **Caching (S13):** TTL-кэш провайдеров (`PROVIDER_CACHE_TTL_SECONDS=60`).
- **UX/UI (S14):** тёмная тема, Pie/Bar-графики на recharts (lazy), поиск/сортировка, кликабельные строки.
- **Settings (S15):** `app_settings`, страница `/settings`, маскировка токенов, runtime-применение конфига.
- **Migration (S15):** массовая миграция `canonical_provider` на GitFlic через фоновый API.
- **Релиз (S16):** docs-consistency audit, тег `v0.3.0` в обоих провайдерах.

**Итоговые метрики:** 116 backend-тестов, 5 frontend-тестов, entry ~84 kB gzip
(графики — отдельный lazy-chunk).

---

## Релиз v0.2.0 — «Observability & Mirror»

**Дата:** 2026-11-05 · **Тег:** `v0.2.0`

Итоги этапа (спринты 7–12):

- **Стабилизация (S7):** закрыты KI-001…KI-003 — kill fetch по таймауту, быстрый dirty-check, TTL-кэш compare.
- **Observability (S8):** Prometheus `/api/v1/metrics`, расширенный `/health`, structlog-события.
- **Mirror GitHub ↔ GitFlic (S9):** 9 статусов зеркала, клиенты провайдеров, polling, webhooks с HMAC, UI-секция «Зеркала».
- **Actions (S10):** подтверждённые мутации `fetch/pull/push/stash/push_mirror`, аудит `action_log`, UI-модалка.
- **CI & Notifications (S11):** GitHub Actions CI-статус, desktop-уведомления, инструкция по webhook-туннелю.
- **Релиз (S12):** docs-consistency audit, тег `v0.2.0` в GitHub и GitFlic.

**Итоговые метрики:** 107 backend-тестов, 3 frontend-теста, entry bundle ~83 kB gzip;
Docker-сканирование `C:/Projects` через volume `/projects` (34 репозитория на dev-машине).

---

## Релиз v0.1.0 — MVP «Situational Awareness»

**Дата:** 2026-11-05 · **Тег:** `v0.1.0`

Что вошло в MVP:

- **Discovery** — поиск `.git` в `SCAN_ROOTS` с ограничением глубины и ignore-списком; запись `scan_runs`.
- **Status** — pygit2-снимок: ветка, upstream, detached, `modified/staged/untracked/conflicted`, `ahead/behind`.
- **Fetch** — `git fetch --all --prune` с таймаутом, graceful `remote_status=unavailable`, пересчёт через `rev-list`.
- **Dashboard** — сводка, фильтры, список репозиториев, track/untrack, детали с коммитами.
- **Recommendations** — команды по состоянию (commit/stash, rebase, push, pull, set-upstream) с копированием в UI; ничего не выполняется автоматически.
- **Docker** — Compose: backend (Python 3.12 + libgit2 + Alembic) и frontend (Node 20 build → nginx), SQLite-volume.
- **Brand** — палитра M3, Inter/Manrope, логотип из бренд-бука.

**Итоговые метрики:** 59 backend-тестов, 2 frontend-теста, entry bundle 83.3 kB gzip.

---

## Спринт 1: Discovery & Data Model

**Период:** 2026-11-03 — 2026-11-04
**Статус:** ✅ Завершён

### Задачи
- [x] S1-001: Модели `Repository`, `RepositoryStatus`, `ScanRun`
- [x] S1-002: Discovery Service (рекурсивный обход, `SCAN_DEPTH`, `SCAN_IGNORE`)
- [x] S1-003: API `/scan`, `/repositories`
- [x] S1-004: Тесты discovery на tmp-репозиториях

### Метрики
- Backend-тесты: 11 passed
- Найдено репозиториев в тестовом дереве: 100% корректно

---

## Спринт 2: Git Status & Каноническая модель

**Период:** 2026-11-04
**Статус:** ✅ Завершён

### Задачи
- [x] S2-001: `pygit2`-бэкенд: `status()`, dirty-разбор, detached, upstream
- [x] S2-002: Каноническая классификация `current/behind/ahead/diverged/dirty/...`
- [x] S2-003: `GET /repositories/{id}/status`
- [x] S2-004: Тесты на всех состояниях (8 сценариев)

### Метрики
- Backend-тесты: 30 passed
- Все 8 состояний покрыты тестами на реальных tmp-репозиториях

---

## Спринт 3: Remote Comparator & Fetch

**Период:** 2026-11-04
**Статус:** ✅ Завершён

### Задачи
- [x] S3-001: `git fetch --all --prune` с таймаутом
- [x] S3-002: `rev-list --left-right --count` → `ahead/behind`
- [x] S3-003: `remote_status` (ok/unavailable/stale)
- [x] S3-004: `GET /repositories/{id}/compare` и `/log` (pygit2)
- [x] S3-005: Тесты с bare-repo как remote

### Метрики
- Backend-тесты: 37 passed
- Fetch на локальных репозиториях: < 2 с

---

## Спринт 4: Dashboard & Frontend

**Период:** 2026-11-04 — 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S4-001: `GET /dashboard` — сводка
- [x] S4-002: Фильтры «Требуют внимания», «Не отслеживаются»
- [x] S4-003: Секция «Не отслеживаются» + track/untrack
- [x] S4-004: Детали репозитория (ahead/behind, файлы, коммиты)
- [x] S4-005: Кнопка «Обновить» + кэш `STATUS_TTL_SECONDS`

### Метрики
- Backend-тесты: 41 passed
- Frontend-тесты: 2 passed
- Entry bundle: 83.3 kB gzip

---

## Спринт 5: Recommendations & Полировка

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S5-001: `RecommendationService` — команды на основе состояния
- [x] S5-002: `GET /repositories/{id}/recommendations`
- [x] S5-003: Read-only аудит: ни одна операция не мутирует рабочую директорию
- [x] S5-004: Docker Compose + `.env.example`

### Метрики
- Backend-тесты: 59 passed
- Read-only аудит: 10 проверок passed
- Docker: `docker compose up -d --build`, UI на порту 3000

---

## Спринт 6: Релиз v0.1.0

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S6-001: Финальные проверки (ruff, mypy, pytest, typecheck, lint, test, build)
- [x] S6-002: Документация (README, SPEC, ARCHITECTURE, USER_GUIDE, GETTING_STARTED, RELEASES, CHANGELOG)
- [x] S6-003: Docs-consistency audit
- [x] S6-004: Тег `v0.1.0` + зеркалирование в GitFlic

### Метрики
| Показатель | Значение |
|------------|----------|
| Backend-тесты | 59 passed |
| Frontend-тесты | 2 passed |
| Entry bundle | 83.3 kB gzip |
| Docker | build + up проверены (UI :3000, API :8000) |

---

## Спринт 7: Стабилизация и технический долг (v0.2.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S7-001 (KI-001): таймаут fetch убивает процесс и логирует подсказку увеличить `FETCH_TIMEOUT`
- [x] S7-002 (KI-002): быстрый dirty-check `git status --porcelain -uno` перед `pygit2.status()`
- [x] S7-003 (KI-003): TTL-кэш `GET /repositories/{id}/compare` (60 с, инвалидация на refresh)
- [x] S7-004: документация (`FETCH_TIMEOUT`, `COMPARE_TTL_SECONDS`, KNOWN_ISSUES, CHANGELOG)

### Метрики
- Backend-тесты: 66 passed
- KI-001…KI-003: **Resolved**

---

## Спринт 8: Monitoring & Metrics (v0.2.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S8-001: Prometheus-метрики fetch/status duration, `repositories_total{state}`, `scan_duration_seconds`
- [x] S8-002: `GET /api/v1/metrics` (Prometheus text format, local-only)
- [x] S8-003: structlog JSON: `fetch_failed`, `status_slow`, `scan_completed`
- [x] S8-004: `/health` — `providers`, кэшированный `git_version`, `db_ok`
- [x] S8-005: `docs/MONITORING.md`, `SPEC §3.1`, тесты observability

### Метрики
- Backend-тесты: 69 passed

---

## Спринт 9: Mirror GitHub ↔ GitFlic (v0.2.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S9-001: поля mirror-политики в `repositories`, таблицы `repository_mirror_status` и `webhook_events`, миграция `003`
- [x] S9-002: `GitHubClient` — `get_branch`, `list_repos`, rate-limit
- [x] S9-003: `GitFlicClient` — `get_branch`, `list_repos`, rate-limit
- [x] S9-004: `MirrorService` — классификация 9 статусов, upsert, candidates
- [x] S9-005: API `/mirror`, `/mirror/refresh`, `PATCH /mirror-policy`
- [x] S9-006: `GET /mirror/candidates`
- [x] S9-007: `MirrorScheduler` (polling `MIRROR_POLL_INTERVAL_SECONDS`)
- [x] S9-008: webhooks GitHub/GitFlic (HMAC, `webhook_events`, инвалидация)
- [x] S9-009: UI — вкладка «Зеркала», панель и модалка политики
- [x] S9-010: метрики `mirror_status_total`, `mirror_check_duration_seconds`
- [x] S9-011: тесты сервиса/API/webhooks
- [x] S9-012: документация (SPEC §3.8, ARCHITECTURE §7, USER_GUIDE)

### Метрики
- Backend-тесты: 90 passed
- Frontend-тесты: 2 passed
- Entry bundle: 83.3 kB gzip

---

## Спринт 10: Мутации с подтверждением (v0.2.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S10-001: `POST /repositories/{id}/actions/{action}` с `confirm=true` (ADR-0003)
- [x] S10-002: действия `pull`, `push`, `stash`
- [x] S10-003: `POST /mirror/actions/push-mirror`
- [x] S10-004: UI «Выполнить» + модалка подтверждения
- [x] S10-005: аудит `action_log` + `GET /admin/actions`
- [x] S10-006: тесты действий на bare-remote

### Метрики
- Backend-тесты: 98 passed
- Frontend-тесты: 3 passed
- Docker: scanning host `C:/Projects` через volume `/projects`

---

## Спринт 11: CI-статус, уведомления, webhook-proxy (v0.2.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S11-001: `GET /repositories/{id}/ci-status` + GitHub Actions клиент + UI-виджет
- [x] S11-002: desktop-уведомления (`plyer`) с настройками и rate-limit
- [x] S11-003: документация webhook-туннеля (cloudflared/ngrok)
- [x] S11-004: инструкция по подключению webhook в GitHub/GitFlic

### Метрики
- Backend-тесты: 107 passed
- Frontend-тесты: 3 passed
- Entry bundle: ~83 kB gzip

---

## Спринт 13: Bulk Actions & Caching (v0.3.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S13-001: `BulkService` — массовые fetch/sync с `asyncio.Semaphore(5)`, фоновые API
- [x] S13-002: TTL-кэш провайдеров (`PROVIDER_CACHE_TTL_SECONDS=60`)
- [x] S13-003: UI Fetch All / Sync Mirrors + polling прогресса
- [x] S13-004: сортировка таблицы и поиск по имени/пути
- [x] S13-005: тесты, SPEC §3.11, CHANGELOG, RELEASES

### Метрики
- Backend-тесты: 111 passed
- Frontend-тесты: 4 passed
- Entry bundle: ~83 kB gzip

---

## Спринт 14: UX/UI & Dashboard Analytics (v0.3.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S14-001: тёмная тема (`dark` класс, localStorage, переключатель, dark-стили компонентов)
- [x] S14-002: аналитика — Pie Chart состояний и Bar Chart `mirror_status` (recharts, lazy)
- [x] S14-003: hover/кликабельные строки, бейджи зеркал
- [x] S14-004: тесты (charts + theme toggle), CHANGELOG/RELEASES

### Метрики
- Backend-тесты: 111 passed
- Frontend-тесты: 5 passed
- Entry bundle: 84.03 kB gzip; charts chunk (lazy): 114.34 kB gzip

---

## Спринт 15: Settings & Mass Migration (v0.3.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S15-001: `AppSetting` + миграция `005`, `SettingsService`, `GET/PATCH /settings`, маскировка токенов
- [x] S15-002: массовая миграция `canonical_provider → gitflic` + 202 background API
- [x] S15-003: страница `/settings`, ссылка в шапке, кнопка «Мигрировать на GitFlic» на дашборде
- [x] S15-004: тесты settings/migration, SPEC/CHANGELOG/RELEASES

### Метрики
- Backend-тесты: 116 passed
- Frontend-тесты: 5 passed
- Entry bundle: 84.18 kB gzip

---

## Спринт 18: Advanced Data Table (v0.4.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S18-001: Zustand `useTableStore` (selection, columns, widths) + persist v1
- [x] S18-002: batch selection + bulk API `repo_ids`
- [x] S18-003: контекстное меню (открыть/fetch/copy path)
- [x] S18-004: управление колонками, resize, моноширинный стиль
- [x] S18-005: тесты (selection/bulk-scope/context menu)

### Метрики
- Backend-тесты: 117 passed
- Frontend-тесты: 7 passed
- Entry bundle: 84.19 kB gzip; Dashboard chunk: 20.27 kB

---

## Спринт 19: Filtering & Saved Views (v0.4.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S19-001: filter chips (статус/зеркало/CI/untracked) + «Очистить всё»
- [x] S19-002: Saved Views (Zustand + persist, применение/удаление)
- [x] S19-003: URL-синхронизация фильтров, сортировки и поиска
- [x] S19-004: CI-агрегат в dashboard для CI-чипов (кэш 60 с)

### Метрики
- Backend-тесты: 117 passed
- Frontend-тесты: 8 passed
- Entry bundle: 84.53 kB gzip; Dashboard chunk: 26.36 kB

---

## Спринт 20: Keyboard Navigation & Command Palette (v0.4.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S20-001: Command Palette (`Ctrl/Cmd+K`) с репозиториями, страницами и действиями
- [x] S20-002: навигация по таблице (`↑/↓`, Enter, Space, `/`, Esc) + подсветка
- [x] S20-003: модалка горячих клавиш (`?`) и подсказка в футере

### Метрики
- Backend-тесты: 117 passed
- Frontend-тесты: 11 passed
- Entry bundle: 85.59 kB gzip; Command Palette chunk (lazy): 4.33 kB

---

## Спринт 21: Visuals, A11y & New Features (v0.4.0)

**Период:** 2026-11-05
**Статус:** ✅ Завершён

### Задачи
- [x] S21-001: A11y-иконки статусов, stale-индикатор (10 мин / remote stale)
- [x] S21-002: Conflict Manager (`/conflicts`, блок для `diverged`); KI-008 Resolved
- [x] S21-003: Telegram-уведомления вместо `plyer`; KI-007 Resolved
- [x] S21-004: contribution heatmap (`/dashboard/heatmap` + UI)
- [x] S21-005: экспорт CSV/JSON (`/repositories/export` + UI)
- [x] S21-006: тесты и документация

### Метрики
- Backend-тесты: 121 passed
- Frontend-тесты: 11 passed
- Entry bundle: 85.59 kB gzip; Dashboard chunk: 30.55 kB
