# IIRuchating — мониторинг и анализ локальных проектов

Интеллектуальный ассистент для разработчика, который держит десятки локальных репозиториев. **Показывает**, что не закоммичено, не запушено и где вы отклонились от удалённого репозитория — вместо того чтобы полагаться на память и ежедневный ритуал `git pull / git push`.

**Версия:** v0.7.0 · **© 2026 RuChating (iilmchat)**

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
- **RU/EN интерфейс** — переключатель языка рядом с темой, выбор сохраняется; даты и числа локализованы через `Intl`.
- **Безопасность** — CVE-сканер зависимостей через OSV.dev (High/Critical, `fixed_version`) и поиск секретов (AWS, GitHub token, JWT, private key) с маскированием.
- **Технический долг и активность** — топ-5 «горячих» файлов по churn и commit frequency за 30 дней (DORA-lite) с ленивым sparkline.
- **Совместная работа** — «Скопировать сводку» в Markdown и экспорт/импорт workspace (Saved Views, колонки) в JSON без токенов и путей.
- **AI-ассистент** — локальный LLM (Ollama/LM Studio) для черновика commit message, объяснения CVE, AI-дайджеста на дашборде, задач для DSH/OpenCode и проверки соединения из настроек; remote endpoint только по opt-in.
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

Backend собирается из `backend/Dockerfile` (Python 3.12, `libgit2`, `git`),
frontend — из `frontend/Dockerfile` (Node 20 build → nginx). SQLite хранится
в `./data` (volume), nginx проксирует `/api` на сервис `backend`.

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

---

## Интерфейс

- **Дашборд** — карточки сводки (всего / чистые / требуют внимания / не отслеживаются), кнопка «Сканировать» и таблица репозиториев: ветка, цветной бейдж состояния, `ahead/behind`, действия.
- **Фильтры** — «Все», «Требуют внимания» (`dirty`, `ahead`, `behind`, `diverged`, `no_upstream`), «Не отслеживаются».
- **Страница репозитория** — путь, ветка, upstream, счётчики изменений, `remote_status`, последние коммиты и блок «Рекомендации» с готовыми командами.
- **Копирование** — кнопка «Копировать» кладёт команду в буфер обмена; приложение **ничего не выполняет** автоматически.
- **Бренд** — фирменная иконка, палитра M3 и шрифты Inter/Manrope из бренд-бука IIRuChating.

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
| Версия | **v0.7.0** (2026-11-06) |
| Спринты | 1–34 (v0.7.0 «AI & Global Analytics») |
| Тесты backend | **225** (pytest, реальные tmp-репозитории; в v0.1.0 — 59) |
| Тесты frontend | **44** (Vitest + Testing Library) |
| Entry bundle | 98.4 kB gzip (+ lazy charts 100.9 kB, AI-дайджест 0.8 kB, задача агента 1.1 kB) |
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

**v0.8.0 «Actionable Dashboard»** — в разработке ([`TODO_V0.8.md`](TODO_V0.8.md)):

- **Sprint 35:** вложенные манифесты зависимостей, README/документы в модалке, рекомендации наверху и всегда свежие, `arhiv-del` возвращён в tracked.
- **Далее:** RU/EN, кликабельные сводки и сворачиваемые разделы (частично готово), Global Dependencies с экосистемами и переходами в проекты, AI-рекомендации на всех экранах, задачи для DSH/OpenCode, профили AI-провайдеров (DeepSeek, OpenRouter, Yandex, GigaChat, GPtunnel).

**v0.8.0+:** синхронизация Saved Views в БД, история статусов и тренды, расширенные интеграции CI/уведомлений и reverse-proxy для webhook.

---

## Лицензия

MIT License · © 2026 RuChating (iilmchat) — [LICENSE](LICENSE)
