# TODO v0.9.0 — Quality Gate, GigaChat & Code Search (RAG)

**Версия:** v0.9.0 «Search & Reliability» (рабочее название)
**Статус:** 📋 Планирование. v0.8.0 выпущен 2026-11-08; спринты 42–44 запланированы.
**Предыдущий этап:** v0.8.0 — [`TODO_V0.8.md`](TODO_V0.8.md)
**Последнее обновление:** 2026-11-08

---

## 1. Зачем v0.9.0

v0.8.0 сделал приложение функционально полным: AI-рекомендации, профили
провайдеров, RU/EN, дубли и README. Следующий риск — **качество и доверие**:
критические пути не защищены E2E-тестами, entry bundle близок к пределу,
GigaChat пока представлен только как OpenAI-совместимый профиль без
специфичного OAuth, а по коду 30+ проектов нельзя искать.

v0.9.0 закрывает эти риски тремя спринтами: **E2E + bundle budget**,
**GigaChat + умный AI-кэш**, **RAG-поиск по коду + релиз**.

### Цели

| # | Цель | Критерий достижения |
|---|------|---------------------|
| G1 | Критические пути защищены E2E | 3 сценария Playwright зелёные локально и в CI (или на доступном runner) |
| G2 | Bundle не растёт | entry bundle **< 90 kB gzip**; budget-check в CI |
| G3 | GigaChat «из коробки» | OAuth 2.0 adapter, токен обновляется автоматически, профиль создаётся из UI |
| G4 | AI не зовёт LLM зря | повторный запрос при неизменном состоянии — из `ai_cache`, без вызова LLM |
| G5 | Поиск по коду | `POST /api/v1/search/code` находит релевантные фрагменты по смыслу, а не только по имени файла |
| G6 | Релиз предсказуем | версии/CHANGELOG/RELEASES/README/SPEC/ARCHITECTURE согласованы, тег и зеркало GitFlic совпадают |
| G7 | Документация не врёт | реализованное и запланированное явно разделены; контракты не противоречат коду |

### Принципы

1. **Read-only по умолчанию.** E2E, RAG и AI-кэш ничего не меняют в чужих
   репозиториях; единственные мутации — существующие `confirm=true` действия.
2. **Local-first.** Эмбеддинги и LLM — локальные (LM Studio/Ollama), remote —
   только явный opt-in (`LLM_ALLOW_REMOTE`, `EMBEDDING_ALLOW_REMOTE`).
3. **Deterministic first, AI second.** Сначала хэши, правила и кэш, потом LLM.
4. **Секреты не уходят.** Токены GigaChat, client_secret, промпты, diff и
   фрагменты кода не логируются и не возвращаются в API.
5. **Никаких новых зависимостей без ADR.** Playwright, анализатор бандла,
   `pgvector`/драйвер эмбеддингов — только с ADR и записью в `docs/adr/`.
6. **Один факт — один источник.** SPEC — контракты, ARCHITECTURE — устройство,
   TODO — план, ADR — причины, KNOWN_ISSUES — ограничения.
7. **Бюджет важнее удобства.** Если фича не влезает в bundle budget — она
   грузится лениво или переносится, а не увеличивает entry.

---

## 2. Спринты

### Спринт 41 — Planning v0.9.0 (✅ Завершён 2026-11-08)

- [x] **S41-001. План v0.9.0.**
  - Создан этот документ; работы разбиты на спринты 42–44.
  - Для каждого спринта зафиксированы задачи, контракты и Definition of Done.
- [x] **S41-002. Документация.**
  - `docs/SPEC.md`: §3.26 (RAG, план) и §3.27 (GigaChat OAuth, план),
    схема `code_chunks`, ограничения и критерии приёмки v0.9.0.
  - `docs/ARCHITECTURE.md`: §21 `CodeSearchService`, §22 `GigaChatProvider`.
  - `docs/KNOWN_ISSUES.md`: KI-017 (память при индексации), KI-018 (короткий
    срок жизни OAuth-токена).
  - `README.md`: анонс v0.9.0 в Roadmap.
- [x] **S41-003. Контракты.**
  - Таблица контрактов и сквозной DoD — ниже, §3–§4.
  - Проверена совместимость с текущими SPEC/ARCHITECTURE; расхождения
    зафиксированы в §7 (в т.ч. отсутствующий ADR-0012 и отсутствие auth).

**DoD:** документ создан; ссылки на SPEC/ARCHITECTURE валидны; запланированное
явно помечено как «план», реализованное — как «выполнено».

---

### Спринт 42 — E2E Testing & Bundle Optimization

**Цель:** защитить три критических пользовательских пути и вернуть entry
bundle под контроль (**< 90 kB gzip**).

#### S42-001. Playwright: фундамент

- [ ] **ADR-0013 «E2E testing with Playwright».** Зафиксировать выбор,
      стоимость зависимости, изоляцию тестовых данных и политику flaky-тестов.
- [ ] Добавить `@playwright/test` в `frontend/devDependencies` (единственная
      новая зависимость спринта; браузеры ставятся `playwright install chromium`).
- [ ] `frontend/playwright.config.ts`:
  - `testDir: ./e2e`, `fullyParallel: false` для git-сценариев;
  - `webServer` поднимает backend (`uvicorn app.main:app --port 8000`) и
    frontend (`vite preview --port 4173`), `reuseExistingServer` — только локально;
  - `E2E_BASE_URL` (default `http://127.0.0.1:4173`), `E2E_API_URL`
    (default `http://127.0.0.1:8000`);
  - trace/video/screenshot — `retain-on-failure`, отчёт `html`;
  - `retries: 0` локально; в CI — 1 с обязательным разбором flaky.
- [ ] Скрипты: `pnpm --dir frontend test:e2e`, `test:e2e:ui`,
      `test:e2e:report`.
- [ ] Изоляция данных:
  - `frontend/e2e/fixtures/` — скрипт создаёт 2–3 **временных** git-репозитория
    (`git init`, коммиты, bare-remote) в `E2E_TMP_DIR`;
  - отдельная БД (`E2E_DB_URL=sqlite+aiosqlite:///.../e2e.db`), `SCAN_ROOTS`
    указывает только на `E2E_TMP_DIR`;
  - `LLM_ENABLED=false` по умолчанию; для AI-сценария — мок-сервер (S42-004);
  - `afterAll` удаляет tmp-репозитории и БД; **реальные проекты не сканируются**.
- [ ] Обновить `docs/TESTING.md`: команды, структура `e2e/`, правило
      «E2E не ходит в сеть и не трогает реальные репозитории».

#### S42-002. Сценарий 1 — onboarding → сканирование → дашборд

> **Трактовка «регистрации».** В v0.8.0 аутентификации нет: приложение
> однопользовательское, bind на `127.0.0.1` (`docs/SPEC.md` §2). Поэтому сценарий
> понимается как **регистрация рабочего пространства (onboarding)**: первый
> запуск → указание/подтверждение `SCAN_ROOTS` → сканирование → дашборд.
> Полноценная учётная запись пользователя (пароли, сессии, роли) в v0.9.0
> **не входит** — это отдельная фича с ADR и изменением SPEC §2.

- [ ] Пустая БД → открыть `/` → пройти onboarding/настройки: проверить
      `SCAN_ROOTS` и сохранить.
- [ ] Нажать «Сканировать» → дождаться завершения (`GET /api/v1/scan/status`).
- [ ] Дашборд показывает сводку и строки репозиториев из фикстуры.
- [ ] Клик по карточке «Требуют внимания» → URL содержит `status=...`,
      список отфильтрован, scroll к таблице.
- [ ] Assert: нет ошибок в console, нет `pageerror`, все сетевые ответы < 500.

#### S42-003. Сценарий 2 — язык и тема

- [ ] Переключить RU → EN: текст меняется без reload,
      `document.documentElement.lang === "en"`,
      `localStorage["iiruchating.locale"] === "en"`.
- [ ] Reload → EN сохраняется.
- [ ] Переключить светлую/тёмную тему: `html.classList.contains("dark")`
      соответствует теме, `localStorage["theme"]` сохраняется.
- [ ] Reload → тема сохраняется; `prefers-color-scheme` не перебивает явный выбор.
- [ ] Assert: нет «смешанного» языка на дашборде и в шапке.

#### S42-004. Сценарий 3 — AI-коммит (мок-LLM) → модалка → копирование

- [ ] Поднять мок OpenAI-совместимого сервера (`/v1/chat/completions`) в
      `frontend/e2e/mock-llm/`; ответ детерминированный:
      `feat(e2e): add mocked commit message`.
- [ ] Создать/активировать профиль провайдера с `base_url` мока;
      `LLM_ENABLED=true`, `LLM_ALLOW_REMOTE=false` (loopback).
- [ ] В фикстуре сделать dirty-изменение → открыть карточку репозитория →
      «Сгенерировать commit message» (`POST /repositories/{id}/ai/commit-message`).
- [ ] Модалка показывает ответ мока; текст редактируемый; кнопка «Копировать»
      кладёт его в clipboard (проверить через `navigator.clipboard.readText()`
      с выданным permission).
- [ ] Assert: LLM вызван ровно один раз; в модалке есть пометка модели;
      никакого коммита не создаётся; при повторном открытии с тем же diff
      работает AI-кэш (после S43-002 — `cached=true`).

#### S42-005. Bundle analysis и ленивые i18n-словари

- [ ] Зафиксировать baseline: entry **99.0 kB gzip**, lazy chunks — charts,
      AI-дайджест, задача агента, профиль AI.
- [ ] ADR-0014 «Bundle analysis & budget»: выбрать анализатор.
      Предпочтительно `rollup-plugin-visualizer` (dev-only, режим `analyze`);
      альтернатива без новой зависимости — `vite build --sourcemap` + разбор
      `dist/assets/*.js`.
- [ ] Скрипт `build:analyze` (`vite build --mode analyze`), отчёт
      `frontend/dist/stats.html`; отчёт не коммитится.
- [ ] Вынести словари **`settings`** и **`repository`** (самые большие:
      ~3.9 kB и ~14.5 kB RU-исходников) в асинхронные чанки:
      - `loadNamespace(locale, ns)` с динамическим `import()`;
      - namespace загружается на route (`Settings`, `RepositoryDetails`) до
        первого рендера (Suspense/route loader), с preload по hover/навигации;
      - `common`/`dashboard`/`components` остаются eager;
      - fallback RU и типизация `TranslationKey` сохраняются; недостающий ключ
        не роняет UI.
- [ ] Budget-check без новой зависимости: `scripts/check-bundle-size.mjs`
      читает `dist/assets/*.js`, считает gzip через `node:zlib`, падает при
      entry > **90 kB gzip**; подключить к `pnpm build` или отдельному
      `pnpm check:bundle`.
- [ ] Проверить, что lazy-чunks не дублируют React/recharts; при необходимости —
      `manualChunks` (vendor, charts, i18n).
- [ ] Записать результат в README/CHANGELOG: entry до/после, список lazy chunks.

**DoD спринта 42:**

- [ ] 3 E2E-сценария зелёные на чистой БД и tmp-репозиториях; flaky = 0.
- [ ] `pnpm --dir frontend test:e2e` работает по документированной команде.
- [ ] Entry bundle **< 90 kB gzip**, budget-check падает при превышении.
- [ ] Словари `settings`/`repository` не входят в entry; RU/EN и тема
      сохраняются после reload.
- [ ] `pnpm typecheck && lint && test && build` — 0; backend-проверки не
      сломаны.
- [ ] ADR-0013/0014 добавлены; `docs/TESTING.md` обновлён.

---

### Спринт 43 — GigaChat & Advanced AI Features

**Цель:** добавить нативный GigaChat OAuth 2.0 и перестать вызывать LLM, когда
состояние репозитория не изменилось.

#### S43-001. GigaChat OAuth adapter

- [ ] Расширить `ai_provider_profiles` (миграция `010`):
      `kind` (`openai_compatible` | `gigachat`, default `openai_compatible`),
      `auth_type` (`api_key` | `oauth`), `client_id`, `client_secret`,
      `oauth_scope`, `oauth_expires_at`, `access_token` (server-only).
      Обратная совместимость: существующие профили — `openai_compatible`/`api_key`.
- [ ] `GigaChatProvider` (`backend/app/services/gigachat_provider.py`):
  - OAuth: `POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth`,
    `Content-Type: application/x-www-form-urlencoded`, `Accept: application/json`,
    `RqUID: <uuid4>`, `Authorization: Basic base64(client_id:client_secret)`,
    body `scope=GIGACHAT_API_PERS` (scope настраивается);
  - ответ `{access_token, expires_at}`; `expires_at` — ms epoch;
  - токен кэшируется в памяти по `profile_id`, обновляется за
    `GIGACHAT_TOKEN_REFRESH_MARGIN_SECONDS` (default 60) до истечения;
  - refresh под mutex (single-flight), при `401` — один принудительный refresh
    и повтор; при повторном `401` — `provider_unauthorized`;
  - TLS: поддержка `GIGACHAT_CA_BUNDLE` (сертификат НУЦ Минцифры); отключать
    проверку сертификата запрещено;
  - ошибки: `invalid_client`, `unsupported_scope`, `provider_unavailable`,
    `timeout`, `provider_unauthorized`, `http_<code>`.
- [ ] Эндпоинт `POST /api/v1/settings/ai-providers/gigachat/auth`:
      принимает `client_id`, `client_secret`, `scope`, `model_name`,
      `profile_name`, `base_url`; выполняет OAuth, создаёт/обновляет профиль и
      делает его активным по `activate=true` (default `false`).
      **Никогда не возвращает** `access_token`/`client_secret`; в ответе только
      `profile_id`, `status`, `expires_at`, `model_name`.
- [ ] `LLMService.resolve()` выбирает адаптер по `kind`; OpenAI-совместимые
      профили работают как раньше. GigaChat-запросы идут в
      `/chat/completions` с `Authorization: Bearer <access_token>`.
- [ ] UI: в модалке профиля — выбор GigaChat, поля client_id/secret/scope,
      кнопка «Авторизоваться», статус «токен действителен до …», повторная
      авторизация; секреты только маскируются.
- [ ] Тесты (mock HTTP, без реальных ключей): успешный OAuth, истёкший токен →
      refresh, 401 → refresh + retry, 429/5xx, TLS/connection error,
      отсутствие токена в ответах/логах, миграция старых профилей.

#### S43-002. Smart AI cache (state hash)

- [ ] `AICacheKeyBuilder`: канонический JSON (sorted keys) → SHA-256 →
      `state_hash`. В ключ входят только факты, влияющие на ответ:
  - рекомендации репозитория: `head_sha`, branch/upstream, ahead/behind,
    dirty-счётчики, hash списка конфликтов, язык, модель, `prompt_version`;
  - дашборд: hash агрегатов (`stats`);
  - global-dependencies: hash отчёта (пакеты/версии/проекты);
  - CVE: `cve_id` + hash `summary` + модель;
  - commit message: hash diff + branch + модель.
- [ ] Ключ: `<feature>:<scope>:<state_hash>:<model>:<prompt_version>`.
      `AI_PROMPT_VERSION` (default `v1`) — ручной инвалидатор при смене промпта.
- [ ] Если ключ найден и TTL не истёк — вернуть `payload`, **не вызывая LLM**,
      `cached=true`, заголовок `X-AI-Cache: hit`. Иначе — вызов, запись,
      `X-AI-Cache: miss`.
- [ ] `refresh=true` (где уже есть) обходит кэш и перезаписывает запись.
- [ ] Single-flight: параллельные одинаковые запросы ждут один вызов LLM
      (`asyncio.Lock` по ключу), остальные получают результат.
- [ ] Метрики: `ai_cache_hits_total{feature}`, `ai_cache_misses_total{feature}`,
      `ai_llm_calls_total{feature,provider,status}`; без промптов и ключей.
- [ ] Не кэшировать `/settings/llm/test` и ошибочные ответы (кроме negative
      cache, если явно решено; по умолчанию — не кэшировать).
- [ ] Тесты: два одинаковых запроса → 1 вызов LLM; изменение состояния →
      новый вызов; истечение TTL; `refresh=true`; dashboard/global/commit;
      отсутствие секретов в ключе и payload.

#### S43-003. UI и наблюдаемость

- [ ] Индикатор «из кэша» + время генерации у AI-блоков (рекомендации,
      дашборд, global advice, CVE).
- [ ] GigaChat: статус авторизации и срок действия токена; при истечении —
      понятная кнопка «Обновить токен», без автоматического спама запросов.
- [ ] Новые строки — только через `t()` (RU/EN), tooltips/aria для новых
      контролов.

#### S43-004. ADR, документация, безопасность

- [ ] ADR-0012 «Multi-provider AI profiles»: создать (в `TODO_V0.8.md` он
      заявлен, но файла в `docs/adr/` нет) и добавить раздел GigaChat OAuth.
- [ ] SPEC §3.27, ARCHITECTURE §22, KNOWN_ISSUES KI-018 — синхронизировать с
      реализацией.
- [ ] Аудит секретов: grep по логам/ответам/`ai_cache`; `client_secret` и
      `access_token` не попадают в `action_log`, structlog и UI.
- [ ] Тесты: миграция, CRUD профиля GigaChat, refresh, маскировка.

**DoD спринта 43:**

- [ ] GigaChat-профиль создаётся и авторизуется через UI/API; токен
      обновляется автоматически; после истечения запрос не падает без
      объяснения.
- [ ] `POST /settings/ai-providers/gigachat/auth` не возвращает секреты;
      повторный вызов обновляет профиль, а не плодит дубликаты.
- [ ] Повторный AI-запрос при неизменном состоянии не вызывает LLM
      (`X-AI-Cache: hit`), состояние изменилось — вызывает.
- [ ] `refresh=true` работает; ошибки LLM не кэшируются.
- [ ] Метрики cache hit/miss и LLM calls доступны в `/metrics`.
- [ ] `ruff`, `mypy --strict`, `pytest -q` — 0 (кроме явно
      задокументированных skip для внешней сети).

---

### Спринт 44 — RAG (поиск по коду) & Release v0.9.0

**Цель:** семантический поиск по README, `docs/` и коду всех tracked-проектов
(в текущем демо — 34 проекта) на PostgreSQL + `pgvector`, затем релиз v0.9.0.

#### S44-001. Инфраструктура pgvector и индексация

- [ ] ADR-0015 «RAG on pgvector»: PostgreSQL-only, выбор модели эмбеддингов,
      размерность, политика хранения и удаления.
- [ ] Миграция `011_code_chunks` (только PostgreSQL):
      `CREATE EXTENSION IF NOT EXISTS vector`; таблица `code_chunks`:
      `id`, `repository_id`, `path`, `chunk_index`, `start_line`, `end_line`,
      `language`, `content`, `content_hash`, `embedding vector(768)`,
      `embedding_model`, `indexed_at`;
      уникальность `(repository_id, path, chunk_index, content_hash)`;
      индексы `repository_id`, `content_hash`, HNSW/IVFFlat по
      `embedding vector_cosine_ops`.
      На SQLite миграция не создаёт таблицу; RAG отвечает `rag_unavailable`.
- [ ] `CodeSearchService` (`backend/app/services/code_search_service.py`):
  - выбор файлов: `README*`, `docs/**/*.md`, `src/**/*` и типовые расширения
    кода; лимит `RAG_MAX_FILE_BYTES` (default 512 KiB), ignore-лист
    (`.git`, `node_modules`, `.venv`, `dist`, `build`, `target`, `vendor`,
    бинарники, lock-файлы, `.env*`, ключи);
  - чанкинг: Markdown — по заголовкам, затем окно ~512 токенов с overlap 64;
    код — по границам функций/классов (эвристика) либо окно строк; сохранять
    `start_line`/`end_line`;
  - эмбеддинги: LM Studio/Ollama OpenAI-compatible `/v1/embeddings`,
    `EMBEDDING_MODEL` (default `nomic-embed-text-v1.5`, 768 dim),
    batch ≤ 32, concurrency ≤ 2, timeout 30 с, retry 3 с backoff;
  - инкрементальность: hash файла (`sha256` + size/mtime) → неизменённые файлы
    пропускаются; изменившиеся чанки переэмбеддируются, старые удаляются;
  - ограничения памяти: потоковое чтение, батчи, `RAG_MAX_CHUNKS_PER_REPO`,
    пауза/отмена; см. KI-017.
- [ ] Эндпоинты индексации:
      `POST /api/v1/search/code/index` (`{repository_ids?, force?}` → `202`,
      job/background task) и `GET /api/v1/search/code/status`
      (`{indexed_repositories, indexed_chunks, last_indexed_at, running, errors}`).
- [ ] Read-only: индексация читает файлы, но не меняет рабочую директорию,
      индекс Git и `.git`; ничего не пишется в чужие репозитории.
- [ ] Тесты: chunker (Markdown/код/строки), ignore-лист, инкрементальность,
      hash, лимиты; интеграционные pgvector-тесты — `@pytest.mark.postgres`
      (skip с причиной, если `POSTGRES_TEST_URL` не задан).

#### S44-002. `POST /api/v1/search/code`

- [ ] Контракт: запрос `{query, repository_ids?, limit?, min_score?, language?}`;
      ответ `{query, model, took_ms, results[], indexed_repositories, stale}`.
- [ ] Валидация: `query` 3–500 символов, `limit` 1–50 (default 10),
      `min_score` 0–1 (default 0.2), `repository_ids` — только tracked.
- [ ] Ранжирование: эмбеддинг запроса → cosine distance (`<=>`), фильтры по
      repository/language, `score = 1 - distance`, сортировка по score.
- [ ] Результат: `repository_id`, `repository_name`, `path`, `start_line`,
      `end_line`, `language`, `snippet` (≤ 400 символов), `score`.
- [ ] `stale=true`, если индекс старше последнего сканирования/HEAD; UI
      предлагает переиндексацию, но не запускает её автоматически.
- [ ] Ошибки: `400` — валидация; `503 rag_unavailable` — нет pgvector/LM Studio;
      `504 embedding_timeout`; `429` — если включён локальный rate-limit.
- [ ] Приватность: запрос, фрагменты и эмбеддинги не логируются; remote
      embeddings — только `EMBEDDING_ALLOW_REMOTE=true`; секреты в snippet
      маскируются/исключаются.
- [ ] Тесты: ранжирование на детерминированных fake-эмбеддингах, фильтры,
      пустой индекс, `stale`, недоступная модель, отсутствие секретов в логах.

#### S44-003. UI поиска

- [ ] Страница/панель «Поиск по коду» + вход из Command Palette
      (`Ctrl+K` → «Найти код…»).
- [ ] Поле запроса, фильтр по проекту/языку, список результатов с путём и
      строками, подсветка snippet, кнопки «Копировать путь»/«Открыть проект».
- [ ] Пустые состояния: «индекс не построен» → ссылка на индексацию;
      «ничего не найдено» → подсказка изменить запрос; ошибка модели — toast.
- [ ] RU/EN, клавиатурная навигация, `aria-live` для результатов, lazy-загрузка
      страницы (bundle budget).

#### S44-004. Release v0.9.0

- [ ] Версии `0.9.0` в backend/frontend/README; CHANGELOG `[0.9.0]`,
      RELEASES (спринты 41–44).
- [ ] Docs-consistency audit: SPEC §3.26/§3.27, ARCHITECTURE §21/§22,
      KNOWN_ISSUES KI-017/KI-018, README Roadmap, TESTING (E2E/RAG).
- [ ] Полные проверки: `ruff check backend/app backend/tests`,
      `mypy backend/app`, `pytest -q`,
      `pnpm --dir frontend typecheck && lint && test && build`,
      `pnpm --dir frontend test:e2e`, bundle budget.
- [ ] Тег `v0.9.0`, GitHub Release, зеркало GitFlic, `SHA(main)` совпадает.
- [ ] Demo: 34 проекта, E2E-сценарии, GigaChat-профиль (mock/реальный),
      smart cache hit, поиск «где у меня настроен Redis?».

**DoD спринта 44:**

- [ ] Индексация README/`docs/`/`src/` всех tracked-проектов завершается без
      OOM на демо-наборе; повторная — инкрементальна.
- [ ] `POST /api/v1/search/code` возвращает релевантные фрагменты с путём и
      строками; на запрос про Redis находит конфигурацию/код, а не только
      файлы с именем `redis`.
- [ ] На SQLite RAG явно недоступен (`503 rag_unavailable`), остальное
      приложение работает.
- [ ] Entry bundle < 90 kB gzip; E2E зелёные; backend/frontend проверки — 0.
- [ ] README/SPEC/ARCHITECTURE/CHANGELOG/RELEASES согласованы; тег и зеркало
      GitFlic указывают на один SHA.

---

## 3. Контракты v0.9.0

| Контракт | Статус | Источник истины |
|----------|--------|-----------------|
| E2E-сценарии и изоляция данных | план (S42) | `docs/TESTING.md`, `frontend/playwright.config.ts` |
| Bundle budget < 90 kB gzip | план (S42) | `docs/ARCHITECTURE.md` §9.3, `scripts/check-bundle-size.mjs` |
| `POST /api/v1/settings/ai-providers/gigachat/auth` | план (S43) | `docs/SPEC.md` §3.27 |
| GigaChat OAuth adapter | план (S43) | `docs/ARCHITECTURE.md` §22 |
| Smart AI cache (`state_hash`, `X-AI-Cache`) | план (S43) | `docs/SPEC.md` §3.25/§3.27, `docs/ARCHITECTURE.md` §15.4 |
| `POST /api/v1/search/code` | план (S44) | `docs/SPEC.md` §3.26 |
| `code_chunks` + pgvector | план (S44) | `docs/SPEC.md` §4, `docs/ARCHITECTURE.md` §21 |
| GigaChat token lifetime | ограничение | `docs/KNOWN_ISSUES.md` KI-018 |
| RAG memory pressure | ограничение | `docs/KNOWN_ISSUES.md` KI-017 |

---

## 4. Сквозной Definition of Done

- [ ] Все задачи спринта `[x]` или перенесены в `KNOWN_ISSUES` с `KI-NNN`.
- [ ] `ruff check backend/app backend/tests` — 0.
- [ ] `mypy backend/app` — 0.
- [ ] `pytest -q` — passed; новые сервисы покрыты тестами; сетевые тесты
      замоканы (кроме локального bare-remote).
- [ ] `pnpm --dir frontend typecheck && lint && test && build` — 0.
- [ ] `pnpm --dir frontend test:e2e` — 3 сценария, 0 flaky.
- [ ] Entry bundle < 90 kB gzip; budget-check в CI/локальной команде.
- [ ] Новые контракты — в SPEC, устройство — в ARCHITECTURE, причины — в ADR.
- [ ] Read-only: RAG/индексация/E2E ничего не меняют в чужих репозиториях.
- [ ] Секреты (GigaChat token/client_secret, промпты, фрагменты кода) не
      попадают в логи, ответы API, `action_log` и `ai_cache` (кроме
      разрешённого текста).
- [ ] RU/EN: новые строки только через `t()`; tooltips/aria для контролов.
- [ ] `CHANGELOG [Unreleased]`, `RELEASES` по спринту, README Roadmap обновлён.
- [ ] Документация различает «реализовано» и «план»; ссылки валидны.

---

## 5. Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| E2E flaky из-за git/времени/анимаций | Высокая | Среднее | tmp-репозитории, фиксированные даты, ожидания по `data-testid`, trace, retries=0 локально |
| E2E сканирует реальные проекты | Низкая | Высокое | `SCAN_ROOTS` только на `E2E_TMP_DIR`, отдельная БД, проверка в `beforeAll` |
| Bundle не влезает в 90 kB | Средняя | Среднее | Ленивые i18n/charts, `manualChunks`, budget-check, перенос фич |
| Ленивый i18n даёт «мигание»/missing keys | Средняя | Среднее | Типизированные namespace, preload route, fallback RU, тест ключей |
| GigaChat OAuth/TLS отличается от ожиданий | Высокая | Среднее | Отдельный adapter, `GIGACHAT_CA_BUNDLE`, mock-тесты, KI-018 |
| GigaChat-токен утекает | Низкая | Высокое | Не возвращать в API, маскировать, не логировать, аудит grep |
| Smart cache отдаёт устаревший совет | Средняя | Высокое | Hash всех входов, `prompt_version`, TTL, `refresh=true`, тесты инвалидации |
| RAG-индексация съедает память | Высокая | Высокое | Батчи, лимиты, инкрементальность, KI-017, HNSW build off-peak |
| Размерность эмбеддингов не совпала | Средняя | Среднее | `EMBEDDING_DIMENSIONS`, валидация модели, полная переиндексация |
| pgvector недоступен (SQLite/CI) | Высокая | Среднее | Явный `503 rag_unavailable`, `@pytest.mark.postgres`, документация |
| Секреты во фрагментах кода | Средняя | Высокое | Ignore `.env`/ключей, redaction snippet, не логировать запросы |
| Release scope creep | Средняя | Среднее | Фиксированный список §6, перенос в v0.9.1 |

---

## 6. Вне scope v0.9.0

- Полноценная аутентификация/регистрация пользователей, роли и сессии
  (SPEC §2: один пользователь; отдельная фича с ADR).
- Автоматическое изменение кода по результатам RAG/LLM.
- Облачные векторные БД, remote embeddings по умолчанию, синхронизация индекса
  между машинами.
- Полноценный редактор кода/просмотр файлов в UI (только snippet + путь).
- GigaChat image generation, биллинг токенов и квоты провайдеров.
- Транзитивные зависимости, SBOM, лицензионный аудит.
- Полное сканирование истории Git на секреты (gitleaks/trufflehog).
- Синхронизация Saved Views в БД (перенос из v0.8.0, кандидат v0.9.1+).

---

## 7. Решения и открытые вопросы

1. **«Регистрация пользователя» в E2E.** В текущем SPEC аутентификации нет;
   сценарий трактуется как onboarding рабочего пространства. Если нужна именно
   учётная запись — требуется отдельный ADR и изменение SPEC §2 (не входит в
   v0.9.0).
2. **RAG только на PostgreSQL.** SQLite остаётся полноценным для остальных
   функций; поиск по коду на SQLite — `503 rag_unavailable`. Альтернатива
   (отдельный SQLite-индекс) не берётся в v0.9.0.
3. **Модель эмбеддингов.** Default — локальная `nomic-embed-text-v1.5` (768).
   Смена размерности требует миграции/переиндексации; параметр
   `EMBEDDING_DIMENSIONS` валидируется при старте.
4. **GigaChat scope/TLS.** Default scope `GIGACHAT_API_PERS`; для B2B/CORP —
   настройка профиля. Сертификат НУЦ Минцифры — через `GIGACHAT_CA_BUNDLE`;
   `verify=False` запрещён.
5. **Новые зависимости.** Playwright (ADR-0013), анализатор бандла (ADR-0014),
   pgvector/клиент эмбеддингов (ADR-0015). Без ADR зависимости не добавляются.
6. **ADR-0012.** В `TODO_V0.8.md` заявлен, но в `docs/adr/` отсутствует;
   создать в S43-004 и зафиксировать multi-provider + GigaChat OAuth.

---

## 8. Что уже сделано в S41 (документация)

| Файл | Изменение |
|------|-----------|
| `TODO_V0.9.md` | создан: спринты 41–44, DoD, риски, контракты |
| `docs/SPEC.md` | §3.26 RAG (план), §3.27 GigaChat OAuth (план), схема `code_chunks`, ограничения, критерии v0.9.0, Roadmap |
| `docs/ARCHITECTURE.md` | §21 `CodeSearchService`, §22 `GigaChatProvider`, обновлён §23 |
| `docs/KNOWN_ISSUES.md` | KI-017 (память RAG), KI-018 (срок жизни OAuth-токена) |
| `README.md` | анонс v0.9.0 в Roadmap (E2E, bundle, GigaChat, smart cache, RAG) |
