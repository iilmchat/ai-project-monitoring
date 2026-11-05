# IIRuchating — мониторинг и анализ локальных проектов

Интеллектуальный ассистент для разработчика, который держит десятки локальных репозиториев. **Показывает**, что не закоммичено, не запушено и где вы отклонились от удалённого репозитория — вместо того чтобы полагаться на память и ежедневный ритуал `git pull / git push`.

**Версия:** v0.3.0 · **© 2026 RuChating (iilmchat)**

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
по умолчанию в `docker-compose.yml` указано `C:/Projects:/projects`, а
`SCAN_ROOTS=/projects`. Если проекты лежат в другом месте — измените путь
в `volumes` и `SCAN_ROOTS` (или задайте в `.env`). Без этого volume
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
| Версия | **v0.3.0** (2026-11-05) |
| Спринты | 1–16 (v0.3.0 «Productivity & UI») |
| Тесты backend | **117** (pytest, реальные tmp-репозитории; в v0.1.0 — 59) |
| Тесты frontend | **7** (Vitest + Testing Library) |
| Entry bundle | 84.2 kB gzip (+ lazy charts 114 kB) |
| Покрытие | не измерялось (`pytest-cov` не подключён) |
| Лицензия | MIT |

### Roadmap

**v0.4.0 «UX/UI & Productivity»** ([полный план](TODO_V0.4.md)):

- Advanced Data Table: batch selection, управление колонками, контекстное меню, моноширинный стиль.
- Filter chips и Saved Views (фильтры + сортировка + колонки, localStorage/URL).
- Command Palette (`Ctrl/Cmd+K`), горячие клавиши и панель подсказок.
- A11y-иконки статусов, stale-индикатор, Conflict Manager (`diverged`).
- Telegram-уведомления вместо `plyer` для headless/Docker.
- Contribution heatmap и экспорт таблицы в CSV/JSON.

---

## Лицензия

MIT License · © 2026 RuChating (iilmchat) — [LICENSE](LICENSE)