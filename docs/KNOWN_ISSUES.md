# KNOWN_ISSUES — Реестр известных проблем

**Последнее обновление:** 2026-11-11

**Всего проблем:** 24 (активных: 18, решено: 6; KI-015/016 не заводились)

---

## KI-001 · Resolved · Med · git/fetch · Нет таймаута на fetch для больших репозиториев

**Описание:** `git fetch` на очень больших репозиториях (monorepo, >1 ГБ) может занимать минуты; таймаут 30 с может быть недостаточным, а прерывание fetch оставляет `.git/FETCH_HEAD` в неконсистентном состоянии (безопасно, но следующий fetch начнётся заново).

**Решение (S7-001, 2026-11-05):** `FETCH_TIMEOUT` остаётся настраиваемым; при таймауте `RemoteService` пишет structlog-warning `Fetch timed out after Ns. Consider increasing FETCH_TIMEOUT` с путём репозитория, а `run_git` явно вызывает `proc.kill()` и дожидается завершения процесса, чтобы не оставлять висящих `git fetch`.

**Workaround (исторический):** Увеличить `FETCH_TIMEOUT` (ENV); при таймауте — `remote_status=unavailable`, повторить вручную.

---

## KI-002 · Resolved · Low · git/pygit2 · `repo.status()` на очень больших деревьях может быть медленным

**Описание:** `pygit2.Repository.status()` обходит всю рабочую директорию; на репозиториях с сотнями тысяч файлов (например, `node_modules` внутри репо, если не в `.gitignore`) может занимать секунды. Игнорирование через `.gitignore` работает, но если файлы не игнорируются, статус будет тяжёлым.

**Решение (S7-002, 2026-11-05):** перед тяжёлым `pygit2.status()` выполняется быстрый `git status --porcelain -uno` с таймаутом 2 с (`is_repo_dirty_fast`). Если tracked-изменений нет, `dirty` сразу равен нулю. Если быстрый чек не прошёл/таймаут — используется полный pygit2-разбор. Ограничение: репозиторий с *только* untracked-файлами быстрый путь считает чистым (осознанный trade-off `-uno`).

**Workaround (исторический):** `SCAN_IGNORE` для тяжёлых директорий; кэш статуса (`STATUS_TTL_SECONDS`).

---

## KI-003 · Resolved · Med · remote · GitHub Compare API rate limit (60/час без токена)

**Описание:** Compare API GitHub без `GITHUB_TOKEN` ограничен 60 запросами/час. При большом числе репозиториев и частом обновлении лимит исчерпывается, и `compare` начинает возвращать 403.

**Решение (S7-003, 2026-11-05):** in-memory TTL-кэш `CompareCache` для `GET /repositories/{id}/compare` (ключ `repo_id, base, head`, TTL `COMPARE_TTL_SECONDS=60`); повторные запросы не вызывают pygit2/API. Кэш инвалидируется при `POST /refresh`. Когда в v0.2.0 появится провайдерский Compare API, кэш будет переиспользован для него.

**Workaround (исторический):** Задать `GITHUB_TOKEN` (5000/час); использовать локальный `rev-list` вместо Compare API, когда детали не нужны.

---

## KI-004 · Accepted · Low · environment · Python 3.11 локально, 3.12 в CI

**Описание:** Локальное dev-окружение работает на Python 3.11.8, при этом `docs/SPEC.md` §7 требует 3.12. CI и Docker-образы используют 3.12.

**Решение:** Зафиксировано как принятое расхождение. При локальном запуске `ruff`/`mypy` используют target `py311`, в CI — `py312`.

**План:** Перевести локальное окружение на 3.12 при следующем обновлении toolchain; отдельного кода-фикса не требуется.

---

## KI-005 · Blocked · High · CI · GitHub Actions не запускает job'ы (биллинг)

**Описание:** Все GitHub-hosted job'ы завершаются с аннотацией: «The job was not started because recent account payments have failed or your spending limit needs to be increased». Код `.github/workflows/ci.yml` корректен, проблема на стороне биллинга аккаунта.

**Workaround:** Локальный прогон проверок (`ruff`, `mypy`, `pytest`, frontend-проверки) перед пушем. В будущем — self-hosted runner или GitFlic CI.

**План:** Разблокировать биллинг GitHub (зона владельца) либо перенести CI на альтернативный runner.

---

## KI-006 · Accepted · Low · mirror · GitFlic pull-mirror не работает

**Описание:** Импорт репозитория в GitFlic прошёл успешно, но встроенный pull-mirror выдаёт ошибку доступа к GitHub (приватность/токены/сетевая доступность).

**Решение:** Автоматическое зеркалирование не используется. Синхронизация выполняется вручную через `git push gitflic main` (или `git push --all gitflic`) сразу после пуша в GitHub. Инструкция — в `docs/GETTING_STARTED.md`.

**План:** Пересмотреть при появлении рабочего механизма зеркалирования в GitFlic.

---

## KI-007 · Resolved · Med · notifications · `plyer` не работает в Docker/headless

**Описание:** Desktop-уведомления через `plyer` требуют графической сессии. В Docker и headless-окружениях вызов завершается `notification_failed`, уведомления не доставляются.

**Решение (S21-003):** `plyer` удалён. `NotificationService` отправляет сообщения в Telegram Bot API (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), при отсутствии токенов — fallback в structlog. Rate-limit ошибок remote сохранён (1/час).

---

## KI-008 · Resolved · Low · UI · Нет Conflict Manager

**Описание:** При `state="diverged"` UI показывает только статус, но не список конфликтующих файлов.

**Решение (S21-002):** `GET /repositories/{id}/conflicts` (`git diff --name-only --diff-filter=U`, read-only) и блок «Конфликты» в деталях репозитория для `diverged`.

---

## KI-009 · Accepted · Med · docker · Docker socket требует прав/настройки на Windows

**Описание:** Docker-интеграция v0.5.0 использует Python Docker SDK. В контейнере SDK обращается к `/var/run/docker.sock`, на Windows при локальном запуске — к named pipe `\\.\pipe\docker_engine`. Доступ к pipe может требовать прав администратора или членства в группе `docker-users`; в корпоративных окружениях Docker Desktop может быть запрещён.

**Влияние:** без сокета/npipe блок Docker показывает `status=unavailable` и строку `error` (`Docker daemon not running` / `Docker daemon permission denied`); остальной дашборд работает. Важно: монтирование сокета `:ro` **не** делает Docker API read-only — сокет даёт root-эквивалент на хосте.

**Workaround:** запустить Docker Desktop; для локального Windows не задавать `DOCKER_HOST` (SDK выберет npipe); при необходимости добавить пользователя в `docker-users`; в контейнере — `DOCKER_HOST=unix:///var/run/docker.sock` + `:ro` mount + `DOCKER_PATH_MAP=C:/Projects=/projects`; при запрете Docker — `DOCKER_ENABLED=false`.

**План (Sprint 24):** SDK auto (UDS/npipe), graceful `status=unavailable`, инструкция в `docs/GETTING_STARTED.md`, ADR-0007.

---

## KI-010 · Resolved · Med · dependencies · Rate-limit API PyPI/npm

**Описание:** проверка зависимостей делает запрос на каждый пакет. При большом числе репозиториев и пакетов PyPI/npm могут отвечать 429/503; без кэша это приводит к неполным отчётам и повторным запросам при каждом открытии карточки.

**Влияние:** часть пакетов получает `status=unknown`; при отсутствии кэша ecosystem может быть `unavailable`. HTTP-ответ остаётся 200 (partial report), дашборд не падает.

**Workaround:** не открывать dependency-блок массово; использовать `refresh=true` только для конкретного репозитория; дождаться восстановления лимита.

**Решение (Sprint 25–26):** TTL-кэш 24 ч (`dependency_cache`, переживает перезапуск), concurrency ≤ 4, backoff 0.5/1/2 с, stale-while-revalidate, partial results. Одна стратегия применяется к PyPI и npm; `refresh=true` — только по явному действию пользователя.

---

## KI-011 · Accepted · Med · security · OSV.dev rate-limit и отсутствие SLA

**Описание:** CVE-проверка v0.6.0 (Sprint 28) делает запрос на каждый уникальный `package@version` в OSV.dev. Публичный API не даёт гарантированного SLA и может отвечать 429/5xx или быть недоступным; на репозитории с сотнями зависимостей это даёт заметную задержку и неполный отчёт.

**Влияние:** часть пакетов остаётся непроверенной (`unknown`), ecosystem может получить `status=unavailable`. Ответ остаётся HTTP 200 (partial report), дашборд не падает. Возможна задержка первого запроса до нескольких секунд.

**Workaround:** использовать `refresh=true` только для конкретного репозитория; дождаться восстановления лимита; при недоступности OSV положиться на stale-кэш (6 ч) и повторить позже.

**Решение (Sprint 28):** `security_cache` с TTL 6 ч (включая negative cache), batch-запрос `/v1/querybatch`, concurrency ≤ 4, backoff 0.5/1/2 с, stale-while-revalidate, partial results. `min_severity=high` по умолчанию сокращает объём ответа в UI; `summary` при этом считается по полному набору. При полной недоступности — `unavailable`, без 500.

---

## KI-012 · Accepted · Med · security · Ложные срабатывания Secret Scanner

**Описание:** базовый regex-сканер v0.6.0 (Sprint 28) ищет AWS-ключи, GitHub-токены, JWT и private-key заголовки. Примеры, тестовые фикстуры, документация и случайные высокоэнтропийные строки дают ложные срабатывания; полноценный энтропийный анализ и пользовательские правила в v0.6.0 не реализуются.

**Влияние:** шум в блоке «Безопасность»; возможен соблазн игнорировать реальные находки. Полные значения секретов при этом не показываются — только masked `preview`.

**Workaround:** добавить `# iiruchating:ignore-secret` в строку-исключение (например, в фикстуре) или запросить `?include_secrets=false`; для CI/примеров держать фейковые значения с явным префиксом (`ghp_example...`).

**Решение (Sprint 28):** фиксированный набор правил с `severity`/`confidence`, маскирование, ignore-маркер, отдельный список findings (не смешивать с CVE), лимиты файлов/размера. Энтропийные эвристики и пользовательские правила — кандидаты в v0.7+; при высоком FP-rate правило можно отключить через `SECRET_SCAN_ENABLED`.

---

## KI-013 · Accepted · Med · ai · LLM может отвечать медленно или галлюцинировать

**Описание:** локальные LLM (Ollama/LM Studio) на слабом железе могут отвечать 5–60 секунд, обрывать контекст на большом diff и генерировать невалидное Conventional Commits-сообщение. В CVE-объяснении модель может добавить несуществующий `fixed_version`, CVE или ссылку, если промпт/контекст неполные.

**Влияние:** таймаут генерации, «мусорный» черновик коммита, вводящее в заблуждение объяснение уязвимости. Автоматических мутаций нет, поэтому риск ограничен неверным текстом, который пользователь может принять без проверки.

**Workaround:** использовать модель поменьше/побыстрее; увеличить `LLM_TIMEOUT_SECONDS`; повторить запрос; для CVE — сверять `fixed_version`/ссылки с OSV; всегда проверять сгенерированный commit message перед коммитом.

**Решение (Sprint 32, commit message):** timeout 30 с, remote-guard, ошибки → `503` + toast в UI, сгенерированный текст показывается в редактируемой модалке и не коммитится без явного подтверждения. Circuit breaker и строгая валидация Conventional Commits не реализованы — это кандидаты в Sprint 33+.

**Решение (Sprint 33, CVE):** объяснение строится по переданному `summary` из `SecurityReport`, кэшируется в `ai_cache` на 7 дней; LLM off/remote → `409`, недоступна → `503` + ошибка в модалке. Валидация фактов/ссылок не выполняется автоматически — пользователь должен сверить объяснение с OSV. Галлюцинации полностью не исключаются.

---

## KI-014 · Accepted · High · dependencies · Обновление пакетов конфликтует с локальными изменениями

**Описание:** `pip install --upgrade` меняет окружение backend, а `pnpm update`/`npm update` могут изменить `package.json` и lockfile. На грязном worktree это смешивается с незакоммиченными правками, ломает сборку/тесты и создаёт конфликты при merge; откат не автоматизирован.

**Влияние:** потеря/смешивание локальных изменений, неожиданное изменение lockfile, неработающее окружение после обновления. Команда может завершиться частично успешно (часть пакетов обновлена).

**Workaround:** закоммитить или застейджить изменения до обновления; запускать по одному репозиторию; просматривать `git diff`/lockfile после; иметь резервную копию окружения; при конфликте — ручной откат.

**Решение (Sprint 34):** preflight требует чистый worktree (`409 "Worktree must be clean"`), явный `confirm=true` и предупреждение в UI; определение менеджера (pip/pnpm/npm), timeout 180 с, output cap 10000 символов с redaction, каждая попытка в `action_log`; ADR-0011. Автоматического коммита и отката нет — ответственность за результат у пользователя.

---

## KI-017 · Accepted · High · rag · RAG-индексация больших проектов требует много памяти

**Описание:** индексация README, `docs/` и `src/` всех tracked-репозиториев (в текущем демо — 34 проекта) читает тысячи файлов, режет их на чанки и строит эмбеддинги. Пиковая память складывается из: содержимого текущего батча файлов/чанков, очереди эмбеддингов (batch ≤ 32, concurrency ≤ 2), ответов LM Studio и построения HNSW-индекса `pgvector` (параметр `maintenance_work_mem`). На больших монорепозиториях возможны OOM процесса backend, swap и длительная блокировка БД.

**Влияние:** индексация может упасть в середине, оставить частичный индекс и нагрузить PostgreSQL; поиск будет отдавать `stale=true`/неполные результаты. На слабом железе локальная модель эмбеддингов может не успеть за таймаут.

**Workaround:** индексировать по одному проекту (`repository_ids`), снизить `RAG_BATCH_SIZE`/`RAG_CONCURRENCY`, увеличить `maintenance_work_mem` только на время построения индекса, исключить тяжёлые каталоги, запускать индексацию вне активной работы; при OOM — перезапустить и продолжить инкрементально.

**Реализовано (Sprint 44):** потоковое чтение; лимиты `RAG_MAX_FILE_BYTES`, `RAG_MAX_CHUNKS_PER_REPO`; батчи и backpressure; инкрементальность по hash; HNSW-индекс строится после массовой вставки; фоновые задачи с отменой; метрики памяти/длительности; документация в ADR-0015. Полностью устранить пик памяти на произвольно больших репозиториях в v0.9.0 не гарантируется.

---

## KI-018 · Accepted · Med · ai/gigachat · GigaChat OAuth-токен имеет короткий срок жизни

**Описание:** GigaChat выдаёт OAuth 2.0 `access_token` примерно на 30 минут (`expires_at` в ответе). Токен нужно обновлять заранее, иначе запрос к `/chat/completions` вернёт `401`, а UI покажет ошибку авторизации. Одновременные AI-запросы могут вызвать несколько refresh-запросов и упереться в rate-limit OAuth-сервиса.

**Влияние:** периодические `401`/`provider_unauthorized`, задержка AI-ответа на время refresh, риск блокировки при «шторме» refresh. Секрет/токен не должны попадать в логи при диагностике.

**Workaround:** повторить запрос вручную после обновления токена; проверить `expires_at` в профиле; при массовых ошибках — временно переключиться на OpenAI-совместимый профиль; не запускать параллельные AI-запросы с одним профилем.

**План (Sprint 43):** реализовано. `GigaChatProvider` кэширует токен по
`profile_id`, обновляет его за `GIGACHAT_TOKEN_REFRESH_MARGIN_SECONDS`
(default 60) до истечения, refresh под mutex (single-flight), при `401` — один
refresh + retry; `expires_at` показывается в UI; ошибки
`invalid_client`/`unsupported_scope`/`provider_unavailable` различимы. Тесты —
с mock HTTP, без реальных ключей. Токен и `client_secret` не логируются и не
возвращаются API.

---

## KI-019 · Accepted · High · desktop · Сборка Python-бинарника с pygit2/pgvector под разные ОС

**Описание:** Tauri-приложение запускает backend как PyInstaller-sidecar. В
зависимостях есть нативные компоненты: `pygit2` (libgit2), `asyncpg`, а для RAG —
PostgreSQL + `pgvector`. PyInstaller должен найти и включить `.dll`/`.so`/`.dylib`
libgit2 и скрытые импорты Alembic/asyncpg; на Windows, macOS (Intel/ARM) и Linux
наборы бинарников различаются. `pgvector` — серверное расширение, его нельзя
«встроить» в Python-бинарник без отдельного PostgreSQL.

**Влияние:** sidecar может упасть на чистой машине с `ImportError`/`DLL load
failed`, особенно на macOS ARM и Windows без Visual C++ Runtime. Desktop-сборка
без внешнего PostgreSQL не даёт RAG, хотя остальные функции работают.

**Workaround:** собирать sidecar на целевой ОС в CI-матрице; использовать
one-folder (не one-file) для предсказуемых путей к libgit2; проверять
`ldd`/`otool`/`dumpbin`; документировать, что RAG в desktop требует внешнего
PostgreSQL с pgvector; для macOS — universal2 или отдельные Intel/ARM сборки.

**План (Sprint 48):** spec-файл PyInstaller с hidden imports, CI-сборка
Windows/macOS, smoke-тест на чистой машине, fallback `rag_unavailable` при
отсутствии PostgreSQL. Встроенный PostgreSQL/pgvector — кандидат v1.1.

---

## KI-020 · Accepted · Med · desktop · Хранение JWT в десктопном приложении

**Описание:** в web-режиме токен хранится в `httpOnly` cookie и недоступен JS.
В Tauri webview cookie может сохраняться между запусками, но при использовании
Bearer-токена его нужно где-то хранить. `localStorage` уязвим к XSS; файл в
app data — к чтению другим пользователем ОС. При этом desktop-приложение
single-user и работает на локальной машине.

**Влияние:** компрометация webview/XSS может привести к краже сессии; при
хранении токена в файле — к доступу после смены пользователя ОС. Долгий TTL
увеличивает окно атаки; logout должен очищать хранилище.

**Workaround:** использовать `httpOnly` cookie в web; в desktop — OS keychain
(Windows Credential Manager / macOS Keychain) или Tauri secure storage; короткий
TTL, logout при закрытии приложения, CSP без remote-origin, запрет
`dangerousRemoteDomainIpcAccess`.

**План (Sprint 48/49):** ADR-0016/0017 фиксируют cookie для web и keychain +
Bearer fallback для desktop; тесты на logout/expiry; аудит XSS/CSP в S49;
секреты не логируются и не попадают в артефакты.

---

## KI-021 · Accepted · Med · desktop · SmartScreen предупреждает при установке `.exe`

**Описание:** Windows-инсталляторы v1.0.0 (NSIS `.exe` и MSI) не подписаны
код-сертификатом Authenticode. Windows SmartScreen показывает предупреждение
«Windows protected your PC» / «Unknown publisher» при запуске установщика.

**Влияние:** пользователь может испугаться предупреждения и отменить установку;
корпоративные политики могут блокировать неподписанные бинарники. Автоподпись
в CI без сертификата невозможна.

**Workaround:** нажать «More info» → «Run anyway»; проверять SHA256 артефакта
из GitHub Release; для организаций — подписать своим сертификатом через
`signtool`. Публиковать checksums рядом с релизом.

**План (Sprint 49+):** приобрести/настроить Authenticode-сертификат, добавить
подпись и timestamp в CI, документировать проверку подписи; до этого явно
указывать, что сборка неподписанная.

---

## KI-022 · Accepted · Med · desktop/rag · RAG недоступен в Desktop-версии на SQLite

**Описание:** desktop-приложение по умолчанию использует SQLite в AppData
(`TAURI_MODE=true`). `pgvector` и `code_chunks` — расширение/тип PostgreSQL;
на SQLite RAG-эндпоинты возвращают `503 rag_unavailable`.

**Влияние:** в установленном `.exe`/`.msi` поиск по коду не работает «из
коробки»; для RAG нужен внешний PostgreSQL с расширением `vector` и
`EMBEDDING_*`. Это осознанный trade-off, чтобы не упаковывать PostgreSQL в
sidecar (KI-019).

**Workaround:** запустить PostgreSQL + pgvector (Docker или локально), задать
`DATABASE_URL=postgresql+asyncpg://...` и `EMBEDDING_*` перед запуском desktop;
либо использовать серверный Docker-режим. Остальные функции desktop работают
на SQLite.

**План (v1.1):** рассмотреть встроенный PostgreSQL/pgvector в desktop-сборке
или отдельный «RAG pack»; до этого явно показывать в UI, что RAG требует
внешнего PostgreSQL.

---

## KI-023 · Accepted · High · ai/conflict · LLM может «галлюцинировать» при разрешении сложных конфликтов

**Описание:** AI Conflict Resolver (Sprint 54) отправляет LLM конфликтные
блоки и просит объединить обе стороны. На сложных конфликтах (переименования,
изменённая сигнатура, несколько пересекающихся правок) модель может вернуть
синтаксически валидный, но семантически неверный код или потерять часть
поведения одной из веток.

**Влияние:** если пользователь применит результат без проверки, возможны
регрессии и скрытые баги. Автоматическая запись файла сделала бы проблему
критической, поэтому resolver **никогда не пишет файл сам**.

**Workaround:** ответ всегда помечается `warnings=["verify_before_apply"]`;
UI показывает полный файл в модалке, требует ручного копирования/применения и
напоминает прогнать тесты. Для сложных конфликтов — разрешать вручную.

**Реализовано (Sprint 54):** read-only endpoint, предупреждение в UI, копирование
вместо авто-применения, тесты на неизменность файла и на отказ от traversal.
**Остаётся:** опциональный второй проход LLM с проверкой синтаксиса/линтером.

---

## KI-024 · Accepted · Med · desktop/macos · Сборка macOS требует сертификатов Apple Developer

**Описание:** кросс-платформенная матрица (Sprint 53) собирает `.dmg` на
`macos-latest`. Без Apple Developer ID и notarization Gatekeeper показывает
предупреждение «cannot be opened because the developer cannot be verified»,
а корпоративные политики могут блокировать запуск.

**Влияние:** пользователь macOS не может установить приложение «в один клик»;
автообновления и CI работают, но требуют ручного подтверждения при первом
запуске. Нотаризация требует платного Apple Developer Program и секретов CI.

**Workaround:** открыть `.dmg`, затем Finder → правый клик → «Open»; либо
`xattr -dr com.apple.quarantine /Applications/IIRuchating.app`. Проверять
checksum из GitHub Release.

**План (Sprint 53+):** добавить codesign + notarytool в CI (Secrets
`APPLE_CERTIFICATE`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD`),
публиковать подписанный/нотаризованный `.dmg`; до этого явно указывать
ограничение в README/GETTING_STARTED.

---

## KI-025 · Accepted · High · dependencies/dotnet · XML-парсинг .NET может быть сложным из-за множества форматов

**Описание:** .NET-проекты описывают зависимости не одним способом:
`*.csproj`/`*.fsproj`/`*.vbproj` с `PackageReference`, Central Package
Management через `Directory.Packages.props` (`PackageVersion`,
`VersionOverride`), legacy `packages.config`, а также `Directory.Build.props`,
`Directory.Build.targets` и `Import`. Версии могут задаваться MSBuild-
свойствами (`$(SomeVersion)`), условиями (`Condition`) и вычисляться во время
сборки. Без запуска MSBuild (`dotnet restore`/`msbuild`) часть версий
принципиально неразрешима.

**Влияние:** пакет может отсутствовать в отчёте, получить `unknown` или
неверную версию; CVE-сканер в таком случае честно не считает его проверенным
(`unknown_packages`), но пользователь может воспринять это как «уязвимостей
нет». Разные форматы также повышают риск ошибок парсинга и пропуска
вложенных проектов solutions (`.sln`).

**Workaround:** для проектов с `$(...)`/conditions использовать
`Directory.Packages.props` с литеральными версиями или `dotnet list package
--outdated --no-restore` вручную; трактовать `unknown` как «требует ручной
проверки», а не как «чисто».

**План (Sprint 57):** приоритет источников `VersionOverride` → `Version` →
CPM → `packages.config`; безопасный XML без DTD/сущностей; лимиты размера и
глубины; причины `msbuild_property`/`conditional`/`parse_error` в отчёте;
тесты на реальных .NET-проектах; MSBuild-evaluation и приватные фиды — вне
scope v1.3.0. Документировать ограничение в UI (бейдж «не вычислено»).

---

## KI-026 · Accepted · Med · iac/docker · Dockerfile и compose бывают сложными — парсинг регулярками даёт ложные срабатывания

**Описание:** `Dockerfile` — не формальный язык с публичной грамматикой, а
набор инструкций с продолжениями строк, комментариями, multi-stage сборками,
`ARG`/`ENV`-подстановками, `ONBUILD`, heredoc и нестандартными базовыми
образами. `docker-compose.yml` допускает якоря/алиасы YAML, merge-ключи,
переменные `${VAR}`, профили и разные формы `ports`/`volumes`. Разбор
регулярками или упрощённым state-machine может не увидеть `USER` в
нестандартном месте, неверно определить финальный stage, принять
`127.0.0.1:8080:80` за публичный порт или пропустить bind-mount
`/var/run/docker.sock`, заданный через переменную/алиас.

**Влияние:** false positive раздражает и подрывает доверие к отчёту; false
negative создаёт ложное ощущение безопасности. Особенно рискованны
`privileged`, `network_mode: host`, публикация портов на `0.0.0.0` и запуск
от `root`: пропуск такого finding — security-риск, а ложный critical —
шум. Сложные файлы также могут привести к таймауту/обрезке отчёта.

**Workaround:** трактовать `IAC001`–`IAC008` как эвристики, а не как
сертификацию; проверять `file:line` и `evidence` вручную; для критичных
проектов дополнительно использовать `hadolint`/`docker scout`/`trivy config`
в CI. `unknown`/`parse_error` считать «требует ручной проверки», а не
«безопасно». При сомнении — временно отключить блок через `IAC_ENABLED=false`.

**План (Sprint 64):** построчный state-machine с продолжениями строк,
комментариями и multi-stage; `USER ${VAR}` не угадывается; `FROM scratch`
не требует `USER`; `HEALTHCHECK NONE` трактуется как отсутствие; compose —
только `yaml.safe_load`, short/long form `ports`, `host_ip`, лимиты размера и
200 сервисов; `evidence` ≤ 300 символов и маскирование секретов; severity и
`file:line` в UI; тесты на реальных tmp-репозиториях (root/non-root,
multi-stage, latest/digest, privileged, localhost/public ports, host network,
docker.sock, битый YAML, лимиты). Полноценный Dockerfile AST, registry-проверка
версий base-образов, OPA/Conftest и автоисправления — вне scope v1.5.0.
