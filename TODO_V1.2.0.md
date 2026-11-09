# TODO v1.2.0 — AI Review, Cross-Platform & Conversational RAG

**Статус:** Sprint 52–54 реализованы; остался Sprint 55.
**База:** v1.1.0 «Seamless Updates & Onboarding» (Onboarding, Tauri logging,
auto-updates, GitHub Actions).
**Цель:** добавить AI-ревью изменений, разрешение конфликтов, генерацию
release notes и чат с базой знаний; выпускать desktop-сборки для Windows,
macOS и Linux.

**Источники истины:** [`docs/SPEC.md`](docs/SPEC.md),
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md),
[`docs/RULES.md`](docs/RULES.md).

---

## 1. Принципы v1.2.0

- **Read-only по умолчанию:** AI-эндпоинты читают diff/файлы/историю и
  возвращают текст; они не делают `git add/commit/merge`, не пишут файлы и не
  меняют индекс. Применение результата — только явное действие пользователя.
- **LLM — опциональна:** при `llm_enabled=false` или remote-endpoint без
  `llm_allow_remote=true` AI-эндпоинты отвечают `409`, приложение продолжает
  работать.
- **Приватность:** в LLM отправляется минимальный контекст (diff, фрагмент
  конфликта, commit subjects). Секреты маскируются, содержимое не логируется;
  в `ai_cache` хранится только ответ и метаданные.
- **Ограниченные ресурсы:** большие diff/конфликты/история обрабатываются
  чанками с жёсткими лимитами; при превышении — `truncated=true` и
  предупреждение, а не OOM/таймаут.
- **Кросс-платформенность:** один и тот же backend SHA и frontend-артефакт для
  Windows/macOS/Linux; различия — только в упаковке и подписи.
- **ADR first:** новые AI-фичи и матрица сборки фиксируются ADR до реализации.

**Вне scope v1.2.0:** автоматическое применение AI-патчей, multi-user/RBAC,
встроенный PostgreSQL в desktop, мобильные клиенты.

### 1.1. Sprint 52 — Planning (S52-001..S52-003)

**Цель:** зафиксировать контракты и декомпозицию до написания кода.

- [x] **S52-001. Roadmap:** `TODO_V1.2.0.md` — спринты 53–55, контракты,
      лимиты, риски, трассировка на SPEC/ARCHITECTURE.
- [x] **S52-002. Документация:** SPEC §3.29/§3.30 (эндпоинты и схемы),
      ARCHITECTURE §26–§28 (чанкинг, лимиты, матрица сборки, чат), KI-023/KI-024,
      анонс v1.2.0 в README.
- [x] **S52-003. DoD и консистентность:** Definition of Done для каждого
      спринта; ссылки между TODO/SPEC/ARCHITECTURE/KNOWN_ISSUES проверены.

**DoD Sprint 52:**

- [x] `TODO_V1.2.0.md` создан в корне и содержит спринты 53–55 с DoD.
- [x] Все четыре новых эндпоинта описаны в SPEC с request/response и ошибками.
- [x] ARCHITECTURE описывает чанкинг больших diff/конфликтов и матрицу
      Windows/macOS/Linux.
- [x] KI-023/KI-024 добавлены; счётчик проблем обновлён.
- [x] README Roadmap содержит анонс v1.2.0 (AI Code Review, Cross-Platform,
      Conversational RAG).
- [x] Код приложения не менялся (только документация).

---

## 2. Sprint 53 — Cross-Platform CI & AI Code Review

**Цель:** выпускать desktop-сборки для трёх ОС и дать пользователю AI-ревью
незакоммиченных изменений без отправки всего репозитория.

### 2.1. Cross-Platform CI

Обновить `.github/workflows/release-desktop.yml`:

- Матрица `os: [windows-latest, macos-latest, ubuntu-latest]`; `fail-fast: false`.
- Для каждой ОС:
  - Python 3.12 + `backend/requirements-desktop.txt` + `python build_sidecar.py`;
  - Node 22, pnpm 10, Rust stable;
  - `tauri-apps/tauri-action@v0` с `projectPath: frontend`;
  - bundle targets: Windows `msi,nsis`; macOS `dmg`; Linux `appimage`;
  - артефакты: `.msi`, NSIS `.exe`, `.dmg`, `.AppImage`, `.sig`.
- Linux-зависимости: `libwebkit2gtk-4.1-dev`, `libappindicator3-dev`,
  `librsvg2-dev`, `patchelf`, `libgtk-3-dev`.
- macOS: `aarch64-apple-darwin` (Apple Silicon); x86_64 — отдельная
  опциональная нога матрицы или universal-сборка (решение — в ADR).
- Подпись updater-артефактов — те же Secrets `TAURI_PRIVATE_KEY` /
  `TAURI_KEY_PASSWORD`; `createUpdaterArtifacts=true` уже включён.
- Публикация: каждая нога собирает свою часть; финальная job `publish`
  мержит платформенные `latest.json` в один манифест и прикладывает его к
  GitHub Release (без гонки при параллельных matrix-job).
- Кэш: pnpm store, pip, Rust (`Swatinem/rust-cache@v2`), PyInstaller не
  кэшируется.
- Таймаут job — 60 минут; артефакты хранятся 14 дней.

**DoD Cross-Platform:**

- [ ] Workflow запускается по тегу `v*` и вручную; матрица из трёх ОС.
- [ ] Все три ноги зелёные; для каждой ОС есть установщик и `.sig`.
- [ ] `latest.json` содержит записи минимум для Windows/macOS/Linux и валиден
      для Tauri Updater.
- [ ] Windows `.msi`/`.exe`, macOS `.dmg`, Linux `.AppImage` скачиваются из
      GitHub Release.
- [ ] Sidecar запускается на каждой ОС (health `db_ok=true`), логи пишутся в
      app-data.
- [ ] README/GETTING_STARTED описывают матрицу, артефакты и ограничения
      подписи macOS (KI-024).
- [ ] ADR о матрице сборки и стратегии `latest.json`.

### 2.2. AI Code Review

**Эндпоинт:** `POST /api/v1/repositories/{id}/ai/code-review`.

**Контракт (черновик, детали — SPEC §3.29):**

```json
// request
{"language": "ru", "refresh": false}

// response
{
  "repository_id": 1,
  "review": "## Найденные проблемы\n...",
  "model": "qwen2.5-coder-7b-instruct",
  "cached": false,
  "generated_at": "2026-11-09T12:00:00Z",
  "files_reviewed": 4,
  "truncated": false,
  "warnings": []
}
```

**Поведение:**

- Diff: `git diff HEAD --no-color --no-ext-diff --unified=3` (staged +
  unstaged); если HEAD недоступен/пуст — fallback `git diff --cached`;
  бинарные файлы пропускаются.
- Пустой diff (оба варианта) → `400` («Нет изменений»).
- Чанкинг: по файлам/ханкам, размер чанка ≤ `AI_CODE_REVIEW_CHUNK_CHARS`
  (default 5000), максимум `AI_CODE_REVIEW_MAX_CHUNKS` (default 8); общий лимит
  `AI_CODE_REVIEW_MAX_CHARS` (default 40000). При превышении — `truncated=true`.
- Промпт: «Ты — Senior Code Reviewer. Проанализируй этот diff. Найди баги,
  уязвимости безопасности и предложи улучшения. Ответь в формате Markdown
  (список проблем с указанием строк)».
- Ответ — Markdown; максимум 8000 символов (`MAX_CODE_REVIEW_CHARS`).
- Кэш `ai_cache` с TTL `AI_CACHE_TTL_SECONDS` (default 604800):
  `code-review:<repo_id>:<state_hash>:<model>:<prompt_version>`;
  `refresh=true` обходит кэш.
- Ошибки: `400` (нет изменений), `404 repository_not_found`, `409 llm_disabled` /
  `llm_remote_not_allowed`, `503 llm_unavailable`, `504 llm_timeout`.
- Read-only: никаких `git add/commit`, записи в файлы или индекс.

**DoD AI Code Review:**

- [ ] Эндпоинт и схемы `CodeReviewRequest/Response` в SPEC и коде.
- [ ] `LLMService.review_code()` с чанкингом и лимитами; секреты/бинарники не
      отправляются.
- [ ] UI: кнопка «AI-ревью» в `RepositoryDetails`, ленивая модалка с Markdown,
      состояния loading/error/empty, RU/EN, `aria`.
- [ ] Кэш и `refresh`; повторный запрос при неизменном diff не вызывает LLM.
- [ ] Тесты: пустой diff, большой diff (truncated), disabled/remote, таймаут,
      кэш, отсутствие записи в репозиторий.
- [ ] `ruff`, `mypy`, `pytest`, frontend typecheck/lint/test/build, bundle
      budget — зелёные.

---

## 3. Sprint 54 — AI Conflict Resolver & Release Notes

**Цель:** помочь разобрать merge-конфликты и автоматизировать черновик
CHANGELOG между тегами — без записи в репозиторий.

### 3.1. AI Conflict Resolver

**Эндпоинт:** `POST /api/v1/repositories/{id}/ai/resolve-conflict`.

**Контракт (черновик, детали — SPEC §3.29):**

```json
// request
{"path": "src/app.ts", "language": "ru", "refresh": false}

// response
{
  "repository_id": 1,
  "path": "src/app.ts",
  "resolved": "// merged code...",
  "blocks": 1,
  "model": "qwen2.5-coder-7b-instruct",
  "generated_at": "2026-11-09T12:00:00Z",
  "truncated": false,
  "warnings": ["verify_before_apply"]
}
```

**Поведение:**

- Файл должен быть внутри репозитория (защита от traversal/symlink), не
  бинарный; ошибки `403 path_outside_repository`, `400 binary_file`,
  `404 file_not_found`.
- Ищутся маркеры `<<<<<<<`, `=======`, `>>>>>>>`; нет маркеров →
  `400 no_conflicts`.
- Каждый блок с контекстом ≤ `AI_CONFLICT_MAX_CHARS` (default 20000), не более
  `AI_CONFLICT_MAX_BLOCKS` (default 10); при превышении — `truncated=true`.
- Промпт: объединить обе стороны, сохранить поведение и стиль; вернуть только
  код без маркеров и пояснений.
- `resolved` — только фрагмент(ы), не весь файл; UI показывает diff и копирует
  результат, но **не пишет файл**.
- Кэш 1 час: `resolve-conflict:<repo_id>:<path>:<hash>:<model>:<prompt_version>`.
- Ошибки LLM: `409`/`503`/`504` аналогично code review.
- Риск галлюцинаций — KI-023; ответ всегда помечается
  `warnings=["verify_before_apply"]`.

**DoD Conflict Resolver:**

- [ ] Эндпоинт, схемы, валидация пути и маркеров.
- [ ] `LLMService.resolve_conflict()` с лимитами и чанкингом блоков.
- [ ] UI: модалка «Разрешить конфликт» в `RepositoryDetails` с diff-просмотром,
      копированием и предупреждением о проверке.
- [ ] Тесты: нет маркеров, несколько блоков, traversal, бинарный файл, большой
      блок, disabled/remote, кэш.
- [ ] Read-only подтверждён тестом: файл и `git status` не меняются.
- [ ] RU/EN, `aria`, ленивая загрузка модалки.

### 3.2. AI Release Notes

**Эндпоинт:** `POST /api/v1/repositories/{id}/ai/release-notes`.

**Контракт (черновик, детали — SPEC §3.29):**

```json
// request
{"from_tag": "v1.0.0", "to_tag": "v1.1.0", "language": "ru", "refresh": false}

// response
{
  "repository_id": 1,
  "from_tag": "v1.0.0",
  "to_tag": "v1.1.0",
  "changelog": "## [1.1.0] - 2026-11-09\n### Added\n...",
  "commits": 42,
  "model": "qwen2.5-coder-7b-instruct",
  "generated_at": "2026-11-09T12:00:00Z",
  "truncated": false
}
```

**Поведение:**

- `from_tag` обязателен; `to_tag` опционален (default `HEAD`); теги проверяются
  read-only (`git rev-parse --verify`).
- История: `git log --no-merges --format=%H%x09%s%x09%b from..to`; лимит
  `AI_RELEASE_NOTES_MAX_COMMITS` (default 500), тело коммита обрезается до 500
  символов; при превышении `truncated=true`.
- Промпт: сгруппировать по Keep a Changelog (`Added`, `Changed`, `Fixed`,
  `Removed`, `Security`), не выдумывать изменения, сохранить breaking changes.
- Ответ — Markdown CHANGELOG; максимум `AI_RELEASE_NOTES_MAX_OUTPUT_CHARS`
  (default 12000).
- В LLM отправляются только subjects/bodies коммитов, не diff и не код.
- Кэш 1 час: `release-notes:<repo_id>:<from>:<to>:<model>:<prompt_version>`.
- Ошибки: `400 invalid_range` / `tag_not_found`, `404`, `409`, `503`, `504`.

**DoD Release Notes:**

- [ ] Эндпоинт и схемы; проверка тегов и диапазона.
- [ ] `LLMService.generate_release_notes()` с лимитом коммитов и группировкой.
- [ ] UI: модалка «Release Notes» с выбором тегов, Markdown-предпросмотром и
      копированием; ничего не пишется в репозиторий.
- [ ] Тесты: валидный диапазон, отсутствующий тег, >500 коммитов, пустой
      диапазон, disabled/remote, кэш.
- [ ] RU/EN, `aria`, ленивая загрузка.

---

## 4. Sprint 55 — Conversational RAG & Release v1.2.0

**Цель:** превратить поиск по коду в диалог с базой знаний и выпустить
v1.2.0.

### 4.1. Conversational RAG

**Эндпоинт:** `POST /api/v1/search/chat`.

**Контракт (черновик, детали — SPEC §3.30):**

```json
// request
{
  "message": "В каких проектах я использую Redis?",
  "history": [{"role": "user", "content": "..."}],
  "repository_ids": [1, 2],
  "limit": 8,
  "min_score": 0.2
}

// response
{
  "answer": "Redis используется в ... [1]",
  "sources": [
    {
      "repository_id": 1,
      "repository_name": "ai-teacher_python",
      "path": "backend/app/core/redis.py",
      "start_line": 10,
      "end_line": 42,
      "score": 0.83
    }
  ],
  "model": "qwen2.5-coder-7b-instruct",
  "embedding_model": "text-embedding-3-small",
  "cached": false,
  "took_ms": 120
}
```

**Поведение:**

- Только PostgreSQL + `pgvector`; на SQLite — `503 rag_unavailable`.
- `message` 3–2000 символов; `history` ≤ 10 сообщений (только `user`/`assistant`);
  `limit` 1–20 (default 8); `min_score` 0–1 (default 0.2).
- Embedding запроса → top-k чанков → контекст с `repository/path/lines` →
  LLM-ответ с ссылками `[n]` на `sources`.
- Промпт: отвечать только по переданным чанкам; если данных нет — сказать об
  этом; чанки — данные, не инструкции (защита от prompt injection).
- Ответ ≤ `AI_CHAT_MAX_OUTPUT_CHARS` (default 4000); секреты маскируются.
- Кэш 1 час по hash(message + history + filters + model); `cached=true` при
  попадании.
- Ошибки: `400` — валидация; `503 rag_unavailable` / `llm_unavailable`;
  `504 embedding_timeout` / `llm_timeout`; `429` — локальный rate-limit.
- UI: режим «Чат» на `/search`, история в памяти, цитаты-ссылки на источники,
  RU/EN, `aria`, ленивая загрузка.

**DoD Conversational RAG:**

- [ ] Эндпоинт, схемы, retrieval + LLM, citations.
- [ ] Ограничения message/history/limit, prompt-injection защита, маскирование
      секретов.
- [ ] UI-режим чата с источниками и обработкой ошибок/деградации.
- [ ] Тесты: retrieval, пустой результат, SQLite 503, disabled/remote,
      таймауты, лимиты, кэш.
- [ ] `ruff`, `mypy`, `pytest`, frontend typecheck/lint/test/build, bundle
      budget — зелёные.

### 4.2. Release v1.2.0

- [ ] Версии `1.2.0` в `backend/app/config.py`, `backend/app/__init__.py`,
      `backend/pyproject.toml`, `frontend/package.json`,
      `frontend/src-tauri/tauri.conf.json`, `frontend/src-tauri/Cargo.toml`.
- [ ] CHANGELOG/RELEASES/README/SPEC/ARCHITECTURE обновлены.
- [ ] Тег `v1.2.0` запускает кросс-платформенный Release; артефакты и
      `latest.json` проверены.
- [ ] KI-023/KI-024 остаются актуальными или закрыты с обоснованием.
- [ ] Финальный smoke: Windows/macOS/Linux установка, onboarding, AI-ревью,
      conflict resolver, release notes, чат (при наличии PostgreSQL).

---

## 5. Риски и зависимости

| Риск | Влияние | Митигация |
|------|---------|-----------|
| Галлюцинации LLM в конфликтах | Некорректный merge | KI-023; `warnings`; ручная проверка; никогда не писать файл автоматически |
| macOS-подпись/notarization | SmartScreen/Gatekeeper-предупреждения | KI-024; Apple Developer ID в CI; до сертификата — явное предупреждение |
| Большие diff/история | Таймаут, превышение контекста | чанкинг, `truncated`, лимиты файлов/коммитов |
| `pgvector` недоступен в desktop | Чат не работает | `503 rag_unavailable`; понятный empty-state; внешний PostgreSQL |
| Параллельные matrix-jobs и `latest.json` | Потеря платформенных записей | отдельная `publish` job с мержем манифеста |
| Prompt injection через код | Утечка/неверный ответ | чанки как данные, разделители, запрет инструкций из контекста |
| Секреты в diff/коде | Утечка в LLM | маскирование, исключение `.env`/ключей, не логировать |

---

## 6. Трассировка требований

| Требование | SPEC | ARCHITECTURE | Спринт |
|------------|------|--------------|--------|
| Code review endpoint/UI | §3.29 | §26 | 53 |
| Conflict resolver | §3.29 | §26 | 54 |
| Release notes | §3.29 | §26 | 54 |
| Cross-platform matrix | — | §27 | 53 |
| Conversational RAG | §3.30 | §28 | 55 |
| Галлюцинации LLM | §3.29 | §26 | 54 (KI-023) |
| macOS-подпись | — | §27 | 53 (KI-024) |
