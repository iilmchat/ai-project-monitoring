# Промпт: OpenCode — Bootstrap проекта IIRuchating (git init → GitHub → GitFlic)

> Разовая задача. Запускать в сессии OpenCode из **пустой директории** проекта
> (или из директории, где уже лежат `docs/`). Перед запуском убедиться, что
> `AGENTS.md` и `docs/` доступны локально.

## Роль

Ты — Senior DevOps/Python инженер. Задача — **инициализировать репозиторий и
создать проект в GitHub (private) и GitFlic (mirror), с базовым CI**, чтобы
документация не потерялась.

## Предусловия (проверить перед стартом)

- [ ] `gh` (GitHub CLI) установлен и залогинен (`gh auth status` → logged in)
- [ ] `git` 2.40+
- [ ] `GITFLIC_TOKEN` — есть (для webhook / API; для импорта через web UI не нужен)
- [ ] Директория содержит `docs/` и `README.md` (наши документы)
- [ ] Нет существующего `.git/`

## Шаги

### 1. Локальный `git init`

```bash
git init -b main
# .gitignore: .env, .env.local, *.db, data/, node_modules/, venv/,
#             __pycache__/, dist/, .wheelhouse/, .pytest_cache/, .mypy_cache/
git add .
git commit -m "chore: initial scaffold with documentation

- docs/SPEC.md, ARCHITECTURE.md, RULES.md, TESTING.md, MONITORING.md
- docs/adr/0001..0005
- docs/prompts/opencode-senior-dev.md, dsh-task-decomposition.md, bootstrap-project.md
- AGENTS.md, CONTRIBUTING.md, SECURITY.md, LICENSE (MIT)
- README.md, TODO.md"
```

### 2. Создать GitHub-репозиторий (private)

```bash
# private по умолчанию (большинство проектов приватные)
gh repo create iilmchat/iiruchating --private --source=. --remote=origin --push
```

Проверить:

```bash
gh repo view iilmchat/iiruchating --json isPrivate,defaultBranchRef
# ожидается: {"isPrivate": true, "defaultBranchRef": {"name": "main"}}
```

### 3. Базовый CI (GitHub Actions)

Создать `.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install ruff mypy
      - run: ruff check backend/app backend/tests || true   # backend ещё нет
      - run: mypy backend/app || true
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: corepack enable && pnpm --dir frontend install || true
```

Закоммитить и запушить:

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add minimal GitHub Actions workflow"
git push
gh run list --limit 1
```

### 4. GitFlic mirror (web UI или CLI)

**Вариант A — web UI (рекомендуется для приватных GitHub):**
1. Открыть <https://gitflic.ru/project/import>
2. Ввести `https://github.com/iilmchat/iiruchating.git`
3. Указать GitHub-токен (scope `repo`) — для приватного репозитория
4. Дождаться импорта; проверить, что `main` совпадает с GitHub (`SHA`).

**Вариант B — push mirror (если импорт недоступен):**
```bash
git remote add gitflic https://gitflic.ru/project/ruchating/iiruchating.git
# (создать пустой проект в GitFlic web UI заранее)
git push -u gitflic main
```

### 5. Проверка зеркалирования

```bash
# SHA должен совпадать
git ls-remote origin main   # GitHub
git ls-remote gitflic main  # GitFlic
```

Если SHA совпадают — `mirror_status=in_sync` (для IIRuchating после v0.2.0;
до этого — визуальная проверка).

### 6. Обновить документацию

- `docs/GETTING_STARTED.md`: добавить раздел «Зеркалирование в GitFlic»
  (как импортировать private repo, как обновлять).
- `README.md`: добавить бейдж CI GitHub.

## Definition of Done

- [ ] `main` запушен в GitHub, CI зелёный (или expected-fail: backend ещё нет).
- [ ] Проект импортирован в GitFlic; `SHA(main)` в GitHub == `SHA(main)` в GitFlic.
- [ ] `.gitignore` исключает `.env`, `*.db`, `node_modules/`, `venv/`.
- [ ] Нет секретов в диффе (`git log -p | grep -i token` — пусто).
- [ ] `docs/GETTING_STARTED.md` содержит раздел про зеркалирование.
- [ ] В отчёте — команды, которые выполнялись, и результат (`gh run list`,
  `git ls-remote`).

## Ограничения

- Не менять содержимое `docs/` без явной необходимости.
- Не коммитить `.env` (только `.env.example`).
- Не использовать `--no-verify` (если настроены хуки).
- Если `gh repo create` падает с 403 (лимит/права) — **остановиться** и
  сообщить владельцу, не обходить через `curl` к GitHub API.