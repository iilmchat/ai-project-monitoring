# Правила разработки IIRuchating

> Обязателен к прочтению каждым участником проекта.

## 1. Принципы

- **Read-only по умолчанию.** Любая операция чтения не изменяет рабочую директорию и индекс Git.
- **Факты — от Git, объяснения — от кода.** Статус репозитория определяется только через libgit2/Git, а не эвристиками.
- **Состояние — каноническое.** `current / behind / ahead / diverged / dirty / no_upstream / detached / error` — единая модель для API, UI и рекомендаций.
- **Один факт — один источник.** SPEC — контракты; ARCHITECTURE — устройство; RULES — как делать.
- **Маленькие итерации.** Спринт = одна логическая порция функциональности; в конце — зелёный CI и отчёт.

---

## 2. Ветвление и коммиты

- `main` — всегда зелёная.
- `sprint/N-<slug>`, `fix/KI-NNN-<slug>`.
- Conventional Commits: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`.
- Пример: `feat(discovery): add recursive .git scan with depth limit (S1-002)`.
- Запрещено коммитить секреты, `.env`, сгенерированные файлы.

---

## 3. Код (Backend)

- Python 3.12, `ruff` (line-length 100), `mypy --strict`.
- Async I/O для БД и сети; Git-операции — в `to_thread`/`run_in_executor`, чтобы не блокировать event loop.
- Pydantic v2 для всех входов/выходов API.
- SQLAlchemy 2.0 (`Mapped`, `mapped_column`).
- Ошибки — доменные исключения в `app/errors.py`.
- Логи — `structlog`, JSON, без `print()`.

**Git-специфика:**
- `pygit2` — для `status()` и discovery (быстро, без subprocess).
- `fetch`/`compare` — через `subprocess` (`git`) с таймаутом и обработкой ошибок.
- Никогда не парсить человекочитаемый вывод `git status` — только `--porcelain` или libgit2.

---

## 4. Код (Frontend)

- React 19 + TypeScript strict.
- Zustand для глобального состояния; `useState` для локального.
- Все строки — через i18n (даже если один язык в v0.1).
- Tailwind 4; никаких inline-стилей.
- Route-level code splitting.

---

## 5. Тесты

- Каждый новый модуль — с unit-тестом.
- **Git-тесты — на реальных временных репозиториях** (`tmp_path` + `git init` + коммиты), а не на моках. Это единственный способ проверить `ahead/behind/dirty` достоверно.
- Для `fetch`/remote — мок или локальный bare-repo (`git init --bare`).
- Покрытие backend ≥ 70%, frontend ≥ 60%.
- Flaky-тесты — блокер; заводить KI и чинить.

---

## 6. Документация

- `SPEC.md` — контракты API и БД.
- `ARCHITECTURE.md` — устройство.
- `USER_GUIDE.md` — для пользователя.
- `CHANGELOG.md` — Keep a Changelog.
- `KNOWN_ISSUES.md` — KI-NNN.
- Каждый PR обновляет затронутые документы.

---

## 7. Git-безопасность

- **Не выполнять мутирующие команды без явного подтверждения.** В v0.1.0 мутаций нет вообще.
- `fetch` — read-only для рабочей директории; безопасен.
- `git clean -fd`, `git reset --hard`, `git checkout .` — **никогда** не выполнять автоматически.
- Рекомендации в UI — только текст, без автозапуска.

---

## 8. Чек-лист перед коммитом

- [ ] `ruff check app tests` — 0
- [ ] `mypy app` — 0
- [ ] `pytest -q` — passed
- [ ] `pnpm typecheck && pnpm lint && pnpm test && pnpm build` — 0
- [ ] Нет секретов в диффе
- [ ] Обновлены документы
- [ ] CI зелёный