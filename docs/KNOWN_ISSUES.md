# KNOWN_ISSUES — Реестр известных проблем

**Последнее обновление:** 2026-11-06

**Всего проблем:** 10 (активных: 5, решено: 5)

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

## KI-010 · Accepted · Med · dependencies · Rate-limit API PyPI/npm

**Описание:** проверка зависимостей делает запрос на каждый пакет. При большом числе репозиториев и пакетов PyPI/npm могут отвечать 429/503; без кэша это приводит к неполным отчётам и повторным запросам при каждом открытии карточки.

**Влияние:** часть пакетов получает `status=unknown`; при отсутствии кэша ecosystem может быть `unavailable`. HTTP-ответ остаётся 200 (partial report), дашборд не падает.

**Workaround:** не открывать dependency-блок массово; использовать `refresh=true` только для конкретного репозитория; дождаться восстановления лимита.

**Реализовано (Python, Sprint 25):** TTL-кэш 24 ч (`dependency_cache`, переживает перезапуск), concurrency ≤ 4, backoff 0.5/1/2 с, stale-while-revalidate, partial results. `refresh=true` — только по явному действию пользователя.

**Осталось (Sprint 26):** распространить ту же стратегию на npm-клиент и `package.json`.
