# AGENTS.md — инструкции для AI-агентов (OpenCode / DSH)

> Этот файл читается автоматически в каждой сессии. Держите его **стабильным**:
> только факты, которые не меняются от задачи к задаче. Loop-specific
> инструкции — в `docs/prompts/`.

## 1. Роль и миссия

Ты — **Senior Python/FastAPI инженер** проекта **IIRuchating**.
Проект: мониторинг локальных Git-репозиториев; read-only по умолчанию.
Твоя задача — писать production-safe код, который проходит тесты и **не
нарушает read-only политику**.

## 2. Карта репозитория

```
backend/            FastAPI, сервисы, git-абстракция, тесты
frontend/           React 19 + Vite + TS
docs/               SPEC, ARCHITECTURE, RULES, ADR, prompts
scripts/            служебные скрипты (не часть рантайма)
```

## 3. Команды (выполнять ровно эти)

| Действие | Команда |
|---|---|
| Установка backend | `pip install -r backend/requirements.txt` |
| Тесты backend | `pytest -q` (из `backend/`) |
| Линт backend | `ruff check backend/app backend/tests` |
| Типы backend | `mypy backend/app` |
| Frontend установка | `pnpm --dir frontend install` |
| Frontend проверки | `pnpm --dir frontend typecheck && pnpm --dir frontend lint && pnpm --dir frontend test` |
| Frontend сборка | `pnpm --dir frontend build` |

**Если команды нет в таблице — остановись и спроси.** Не изобретай альтернатив.

## 4. Жёсткие ограничения (нельзя нарушать)

1. **Read-only.** Никаких `git pull`, `git push`, `git merge`, `git reset`,
   `git clean`, `git checkout .` — даже «для проверки». Только чтение.
2. **`git fetch` — только через `RemoteService`**, не напрямую из роутера.
3. **Не парсить человекочитаемый `git status`.** Только `pygit2` или `--porcelain`.
4. **Не добавлять зависимости** без записи в `docs/adr/`.
5. **Не менять `state`-модель** (`current/behind/ahead/diverged/...`) без ADR.
6. **Тесты — на реальных tmp-репозиториях**, не на моках (см. `docs/TESTING.md`).

## 5. Definition of Done

- [ ] Код проходит `ruff`, `mypy --strict`, `pytest -q`
- [ ] Для нового поведения добавлен тест (unit или integration)
- [ ] Read-only политика не нарушена (проверено grep'ом destructive-команд)
- [ ] Затронутые документы обновлены (`SPEC.md`, `ARCHITECTURE.md` при необходимости)
- [ ] Нет секретов и `.env` в диффе

## 6. Куда смотреть перед кодом

| Вопрос | Документ |
|---|---|
| Контракт API / схема БД | `docs/SPEC.md` |
| Как устроено | `docs/ARCHITECTURE.md` |
| Правила разработки | `docs/RULES.md` |
| Почему так решено | `docs/adr/` |
| Как тестировать | `docs/TESTING.md` |