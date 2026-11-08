# IIRuchating — мониторинг и анализ локальных проектов

Интеллектуальный ассистент для разработчика, который держит десятки локальных репозиториев. **Показывает**, что не закоммичено, не запушено и где вы отклонились от удалённого репозитория — вместо того чтобы полагаться на память и ежедневный ритуал `git pull / git push`.

**Версия:** v0.8.0 · **© 2026 RuChating (iilmchat)**

---

## Зачем это нужно

Разработчик с 20+ проектами на диске каждое утро/вечер делает ручной обход: `git status`, `git log`, `git fetch`, `git merge`… Это забывается, а забытое = потерянная работа или неожиданный merge-конфликт. **IIRuchating** сканирует локальные директории, находит все `.git`-репозитории, снимает **локальное состояние** (uncommitted, unpushed, ahead/behind) и **сравнивает** его с удалённым репозиторием (GitHub/GitFlic) — без внесения изменений. Список отслеживаемых проектов управляется, а новые (неучтённые) репозитории автоматически подсвечиваются.

**Стек:** Python 3.12 · FastAPI · SQLite (или PostgreSQL) · pygit2 + git CLI · React 19 (Vite, TS) · Docker Compose.

---

## Ключевые возможности

- **Автообнаружение репозиториев** — рекурсивный поиск `.git/` в заданных корневых директориях (глубина, исключения).
- **Локальный статус** — uncommitted (modified/staged/untracked), unpushed commits (ahead), behind (удалённый впереди), diverged (конфликт), detached HEAD, отсутствие upstream.
- **Сравнение с удалённым** — через `git fetch` (read-only) и `compare API` GitHub/GitFlic определяется точное состояние: `current / behind / ahead / diverged / dirty / no_upstream`.
- **Управляемый список проектов** — явное добавление/исключение репозиториев; неучтённые проекты показываются в отдельной секции «Не отслеживаются».
- **Снимок «последней выкладки»** — что было последним коммитом, куда двигаться дальше (action queue).
- **Подсказки и рекомендации** — что сделать: `git stash && pull`, `commit`, `push`, `rebase` — без автоматического выполнения (read-only по умолчанию).
- **Read-only по умолчанию** — только чтение состояния; мутации (`pull`/`push`/`stash`/`push_mirror`) — по явной кнопке с подтверждением и аудитом.
- **Зеркалирование GitHub ↔ GitFlic** — `mirror_status` (9 состояний), polling, webhooks, настройка политики.
- **Продуктивность и UI** — тёмная тема, интерактивные графики распределения статусов, страница настроек (токены хранятся в БД с маскировкой), массовые операции (Fetch All / Sync Mirrors) и миграция на GitFlic.
- **UX и продвинутый мониторинг** — Command Palette (`Ctrl+K`), продвинутая таблица с чекбоксами и контекстным меню, сохранённые представления (Saved Views), Telegram-уведомления, менеджер конфликтов и график активности (Heatmap).
- **Docker-интеграция** — read-only статус контейнеров проекта (running/stopped, порты, health) через Docker SDK/DooD.
- **Управление зависимостями** — аудит устаревших Python (`requirements.txt` / PyPI) и Node (`package.json` / npm) пакетов с TTL-кэшем 24 ч, табами Python/Node и объединённым отчётом; вложенные манифесты (`backend/`, `frontend/`) находятся автоматически.
- **README и документация** — название и версия проекта из README, модальный просмотр Markdown с переходами по внутренним ссылкам и историей «Назад» (read-only).
- **Действенный дашборд** — кликабельные карточки сводки («9 требуют внимания» → отфильтрованный список), сворачиваемые фильтры/аналитика и человеческие подписи состояний.
- **Мультиязычный интерфейс (RU/EN)** — переключатель языка рядом с темой, выбор сохраняется; даты и числа локализованы через `Intl`.
- **Интеграция с AI-агентами** — генерация Markdown-задач для DSH/OpenCode; **профили AI-провайдеров** (LM Studio, DeepSeek, OpenRouter, GigaChat OAuth) с активацией без перезапуска.
- **E2E-тесты** — Playwright-сценарии onboarding/сканирования, RU/EN + темы и AI-коммита на моках API/LLM; `pnpm --dir frontend test:e2e`.
- **Smart Cache** — LLM-ответы кэшируются по `state_hash` (dashboard, unification, CVE, commit message) и не вызывают модель при неизменном состоянии.
- **RAG-поиск по коду** — семантический поиск по README/docs/src всех tracked-репозиториев на PostgreSQL + `pgvector`; на SQLite API отвечает `503 rag_unavailable`.
- **Desktop-приложение (v1.0.0)** — Tauri + Python sidecar, Windows `.msi`/`.exe`, SQLite в AppData, автоматический запуск/остановка backend без Docker.
- **Безопасность** — CVE-сканер зависимостей через OSV.dev (High/Critical, `fixed_version`) и поиск секретов (AWS, GitHub token, JWT, private key) с маскированием.
- **Технический долг и активность** — топ-5 «горячих» файлов по churn и commit frequency за 30 дней (DORA-lite) с ленивым sparkline.
- **Совместная работа** — «Скопировать сводку» в Markdown и экспорт/импорт workspace (Saved Views, колонки) в JSON без токенов и путей.
- **AI-ассистент** — локальный LLM (Ollama/LM Studio) для черновика commit message, объяснения CVE, AI-дайджеста на дашборде, задач для DSH/OpenCode и проверки соединения из настроек; профили OpenAI-совместимых провайдеров (local/DeepSeek/OpenRouter/Yandex/…), активный профиль переключается без перезапуска; remote endpoint только по opt-in.
- **Глобальный анализ зависимостей** — версии популярных пакетов по всем проектам, закладки «Все/Python/Node», раскрываемый список проектов со ссылками, распределение версий и бейдж «Унифицировать»; AI-совет по выбору версии.
- **Дубли и унификация** — группировка клонов по нормализованному remote URL (`GET /dashboard/duplicates`), блок «Унификация» в карточке проекта с переходом к обновлению пакетов.
- **Безопасное обновление пакетов** — `pip`/`pnpm`/`npm` только по явному подтверждению и на чистом worktree, с аудитом `ActionLog`.
- **Наблюдаемость** — Prometheus-метрики, расширенный `/health`, JSON-логи.
- **CI и уведомления** — статус GitHub Actions и desktop-уведомления о проблемах.
- **Веб-дашборд** — обзор всех репозиториев, фильтры «требуют внимания», детали по каждому.

---

## Быстрый старт

```bash
git clone https://github.com/iilmchat/ai-project-monitoring.git
cd ai-project-monitoring
cp .env.example .env            # укажите SCAN_ROOTS, GITHUB_TOKEN (опционально)
```

### Docker Compose

```bash
docker compose up -d --build
```

- Веб-интерфейс: <http://127.0.0.1:3000>
- API (напрямую): <http://127.0.0.1:8000/api/v1/health>
- Вход: `admin` / `admin` (задайте `ADMIN_PASSWORD` и `AUTH_JWT_SECRET` в `.env`
  перед доступом по LAN).

Backend собирается из `backend/Dockerfile` (Python 3.12, `libgit2`, `git`),
frontend — из `frontend/Dockerfile` (Node 20 build → nginx). Docker Compose
поднимает PostgreSQL 16 + `pgvector` (volume `./pgdata`), backend ждёт healthy
`db` и выполняет `alembic upgrade head`; nginx проксирует `/api` на сервис
`backend`. RAG-поиск по коду доступен на PostgreSQL (см.
[GETTING_STARTED.md](docs/GETTING_STARTED.md#31-использование-postgresql-и-rag)).

Для сканирования в Docker каталог с проектами монтируется в контейнер:
по умолчанию `${PROJECTS_ROOT:-C:/Projects}:/projects`, а `SCAN_ROOTS=/projects`.
Если проекты лежат в другом месте — задайте `PROJECTS_ROOT` (источник volume)
и `DOCKER_PATH_MAP=<host-root>=/projects` в `.env`. Без этого volume
сканирование найдёт 0 репозиториев.

### Локально без Docker

```bash
# backend
cd backend && python -m venv venv && .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# frontend
pnpm --dir frontend install
pnpm --dir frontend dev
```

Подробно — [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

### Сборка десктопного приложения (Tauri)

Требования: Rust toolchain (`rustup`), WebView2 (Windows), Python venv с
`backend/requirements-desktop.txt`.

```bash
# 1. Зависимости frontend + Tauri CLI
pnpm --dir frontend install

# 2. Python-sidecar (PyInstaller, один .exe без консоли)
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements-desktop.txt
python build_sidecar.py
cd ..

# 3. Tauri build (Windows: .msi + NSIS .exe)
pnpm --dir frontend desktop:build
```

Артефакты:

- `frontend/src-tauri/target/release/bundle/msi/IIRuchating_1.0.0_x64_en-US.msi`
- `frontend/src-tauri/target/release/bundle/nsis/IIRuchating_1.0.0_x64-setup.exe`

Sidecar запускается на свободном `127.0.0.1:<port>`; данные и логи —
в `%APPDATA%/IIRuchating` (`backend.log`). Desktop по умолчанию использует
SQLite; RAG доступен только при внешнем PostgreSQL + `pgvector`. Вход по
умолчанию `admin` / `admin` (смените `ADMIN_PASSWORD`/`AUTH_JWT_SECRET`).
Для разработки: `pnpm --dir frontend desktop:dev`.

---

## Интерфейс

- **Дашборд** — карточки сводки (всего / чистые / требуют внимания / не отслеживаются), кнопка «Сканировать» и таблица репозиториев: ветка, цветной бейдж состояния, `ahead/behind`, действия.
- **Фильтры** — «Все», «Требуют внимания» (`dirty`, `ahead`, `behind`, `diverged`, `no_upstream`), «Не отслеживаются».
- **Страница репозитория** — путь, ветка, upstream, счётчики изменений, `remote_status`, последние коммиты и блок «Рекомендации» с готовыми командами.
- **Копирование** — кнопка «Копировать» кладёт команду в буфер обмена; приложение **ничего не выполняет** автоматически.
- **Бренд** — фирменная иконка, палитра M3 и шрифты Inter/Manrope из бренд-бука IIRuChating.

---

## Десктопное приложение (Windows/macOS)

В v1.0.0 приложение можно установить как обычную desktop-программу: React UI
и FastAPI backend упакованы в Tauri + Python-sidecar. Docker, Python и Node на
машине пользователя **не нужны**.

### Windows: скачать и установить

1. Откройте [GitHub Releases](https://github.com/iilmchat/ai-project-monitoring/releases/tag/v1.0.0).
2. Скачайте один из файлов:
   - `IIRuchating_1.0.0_x64-setup.exe` — NSIS-установщик;
   - `IIRuchating_1.0.0_x64_en-US.msi` — MSI для групповых политик.
3. Запустите установщик. Windows SmartScreen может показать
   «Unknown publisher», так как бинарники пока не подписаны код-сертификатом
   (KI-021). Нажмите «More info» → «Run anyway».
4. Запустите **IIRuchating**. Появится splash, затем экран входа.
5. Вход по умолчанию: **`admin` / `admin`**. Смените пароль через
   `ADMIN_PASSWORD` (см. ниже).

Данные и логи: `%APPDATA%\IIRuchating` (`iiruchating.db`, `backend.log`).
Sidecar запускается на свободном `127.0.0.1:<port>` и останавливается при
закрытии приложения.

### macOS

Готовый `.dmg` требует сборки на macOS (Apple Silicon/Intel) с подписью и
notarization; на Windows его собрать нельзя. Пайплайн:

```bash
pnpm --dir frontend install
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements-desktop.txt
python build_sidecar.py
cd ../frontend
pnpm desktop:build
```

Результат — `frontend/src-tauri/target/release/bundle/dmg/*.dmg`. Для
распространения нужен Apple Developer ID и notarization.

### Сборка из исходников (Windows)

```bash
pnpm --dir frontend install

cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements-desktop.txt
python build_sidecar.py
cd ..

pnpm --dir frontend desktop:build
```

Артефакты:

- `frontend/src-tauri/target/release/bundle/msi/IIRuchating_1.0.0_x64_en-US.msi`
- `frontend/src-tauri/target/release/bundle/nsis/IIRuchating_1.0.0_x64-setup.exe`

### Ограничения desktop

- **RAG:** desktop по умолчанию использует SQLite, поэтому RAG недоступен
  (`503 rag_unavailable`). Для RAG задайте внешний
  `DATABASE_URL=postgresql+asyncpg://...` с `pgvector` и `EMBEDDING_*` (KI-022).
- **Auth:** desktop использует Bearer-токен в памяти; после перезапуска может
  потребоваться повторный вход (KI-020). Для стабильных сессий задайте
  `AUTH_JWT_SECRET`.
- **SmartScreen:** установщики не подписаны (KI-021).
- **Консоль:** sidecar и дочерние процессы (`git`, `pip`, `pnpm`) запускаются
  без консольного окна на Windows (`CREATE_NO_WINDOW`).
- Docker остаётся серверным вариантом с PostgreSQL/RAG.

---

## Тестирование

```bash
# backend
cd backend
pytest -q
ruff check app tests
mypy app

# frontend: unit-тесты (Vitest + Testing Library)
pnpm --dir frontend test

# frontend: E2E (Playwright, Chromium)
pnpm --dir frontend test:e2e
pnpm --dir frontend test:e2e:ui      # интерактивный режим
pnpm --dir frontend test:e2e:report  # открыть HTML-отчёт
```

E2E-сценарии лежат в `frontend/e2e/` и перехватывают запросы через Playwright
`page.route()`: backend, БД и локальная LLM **не нужны**, реальные репозитории не
сканируются. Первый запуск требует установки браузера:

```bash
pnpm --dir frontend exec playwright install chromium
```

Подробности — [docs/TESTING.md](docs/TESTING.md).

---

## Документация

| Документ | Назначение |
|----------|------------|
| [SPEC.md](docs/SPEC.md) | Контракты API, схема БД, статусы, критерии приёмки |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Как устроено: слои, discovery, git-абстракция, сравнение |
| [USER_GUIDE.md](docs/USER_GUIDE.md) | Инструкция разработчику |
| [GETTING_STARTED.md](docs/GETTING_STARTED.md) | Развёртывание |
| [RULES.md](docs/RULES.md) | Правила разработки |
| [CHANGELOG.md](docs/CHANGELOG.md) | История версий |
| [KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | Реестр проблем (KI-NNN) |
| [RELEASES.md](docs/RELEASES.md) | Журнал спринтов |

---

## Статус

| Показатель | Значение |
|------------|----------|
| Версия | **v1.0.0** (2026-11-08) |
| Статус | **v1.0.0 «Secure Desktop» выпущен** |
| Спринты | 1–49 |
| Тесты backend | **254** (pytest, реальные tmp-репозитории; в v0.1.0 — 59) |
| Тесты frontend | **45** unit (Vitest + Testing Library) + **3** E2E (Playwright) |
| Entry bundle | **89.62 kB gzip** (+ lazy charts 100.9 kB, поиск кода 2.1 kB, логин 1.0 kB, AI-дайджест 0.8 kB) |
| Desktop | Windows `.msi` + NSIS `.exe`; macOS — сборка на macOS (CI/notarization) |
| Покрытие | не измерялось (`pytest-cov` не подключён) |
| Лицензия | MIT |

### Roadmap

**v0.5.0 «Observability & Dependency Management»** — выпущен 2026-11-06
([`TODO_V0.5.md`](TODO_V0.5.md)):

- **Dark Charts:** M3-палитра для `recharts` (оси, тултипы, легенды) в светлой и тёмной темах.
- **Docker:** read-only статус контейнеров проекта (running/stopped, порт, health) в карточке репозитория.
- **Dependencies:** проверка устаревших Python (`requirements.txt`) и Node (`package.json`) пакетов с TTL-кэшем 24 ч.

**v0.6.0 «Security, Insights & Collaboration»** — выпущен 2026-11-06
([`TODO_V0.6.md`](TODO_V0.6.md)):

- **Supply Chain Security (Sprint 28):** CVE-проверка Python/Node-зависимостей через OSV.dev (High/Critical) и базовый regex-поиск секретов в рабочей директории.
- **Tech Debt & Insights (Sprint 29):** топ-5 «горячих» файлов по churn и commit frequency в `main` за 30 дней (DORA-lite, sparkline).
- **Collaboration & Release (Sprint 30):** «Скопировать сводку в Markdown», экспорт/импорт workspace (Saved Views, колонки) в JSON и релиз `v0.6.0`.

**v0.7.0 «AI & Global Analytics»** — выпущен 2026-11-06
([`TODO_V0.7.md`](TODO_V0.7.md)):

- **LLM Provider & AI Commit Messages (Sprint 32):** Ollama/LM Studio через OpenAI-совместимый API, настройки в UI, генерация Conventional Commits по `git diff` с подтверждением в модалке.
- **AI Security Insights & Global Dashboard (Sprint 33):** объяснение CVE через локальный LLM и глобальная сводка версий популярных пакетов с кандидатами на унификацию.
- **Automated Dependencies & Release (Sprint 34):** обновление пакетов по явному подтверждению с preflight и `ActionLog`, финальный аудит и релиз `v0.7.0`.

**v0.8.0 «AI Workspace»** — выпущен 2026-11-08
([`TODO_V0.8.md`](TODO_V0.8.md)):

- **Sprint 35:** вложенные манифесты зависимостей, README/документы в модалке, рекомендации наверху и всегда свежие.
- **Sprint 36:** RU/EN i18n, кликабельные сводки, сворачиваемые разделы, человеческие подписи.
- **Sprint 37:** дубли по remote URL, AI-советы по унификации, блок «Унификация».
- **Sprint 38:** AI-дайджест дашборда, задачи для DSH/OpenCode, проверка LLM.
- **Sprint 39:** профили AI-провайдеров (LM Studio, DeepSeek, OpenRouter, Yandex и др.).

**v0.9.0 «Stability & RAG»** — выпущен 2026-11-08
([`TODO_V0.9.md`](TODO_V0.9.md)):

- **Sprint 42 — E2E & Bundle:** Playwright-сценарии (onboarding → сканирование →
  дашборд; RU/EN + тема; AI-коммит с мок-LLM) и entry bundle **< 90 kB gzip**
  за счёт ленивых i18n-словарей `Settings`/`RepositoryDetails`.
- **Sprint 43 — GigaChat & Smart Cache:** нативный GigaChat OAuth 2.0 adapter
  с автообновлением токена и smart-кэш AI-ответов по хэшу состояния
  репозитория (без повторного вызова LLM).
- **Sprint 44 — RAG & Release:** индексация README/`docs/`/`src/` всех
  tracked-проектов в PostgreSQL + `pgvector`, семантический поиск
  `POST /api/v1/search/code` («где у меня настроен Redis?») и релиз `v0.9.0`.

**v0.9.0+:** синхронизация Saved Views в БД, история статусов и тренды,
расширенные интеграции CI/уведомлений и reverse-proxy для webhook.

**v1.0.0 «Secure Desktop»** — выпущен 2026-11-08
([`TODO_V1.0.md`](TODO_V1.0.md)):

- **Sprint 45 — PostgreSQL & RAG:** Docker Compose с `pgvector`, индексация и
  семантический поиск по коду; SQLite fallback `503 rag_unavailable`.
- **Sprint 46 — Planning:** roadmap v1.0.0, контракты Auth/Tauri.
- **Sprint 47 — Single-User Authentication:** ✅ bcrypt, JWT, httpOnly cookie,
  middleware, login/me/logout, protected routes; `admin` / `admin` по умолчанию.
- **Sprint 48 — Tauri Desktop App:** ✅ Windows `.msi`/`.exe`, Python-sidecar,
  SQLite в AppData, автоматический запуск/остановка backend без Docker.
- **Sprint 49 — Release v1.0.0:** ✅ аудит безопасности, версии 1.0.0,
  документация, GitHub Release и GitFlic mirror.

---

## Лицензия

MIT License · © 2026 RuChating (iilmchat) — [LICENSE](LICENSE)
