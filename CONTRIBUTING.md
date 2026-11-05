# CONTRIBUTING — как контрибьютить в IIRuchating

## 1. Ветки

- `main` — всегда зелёная.
- `sprint/N-<slug>` — рабочая ветка спринта.
- `fix/KI-NNN-<slug>` — исправление известной проблемы.

## 2. Коммиты

Conventional Commits: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`.

Пример:
```
feat(discovery): add depth-limited recursive .git scan (S1-002)
```

Обязательно: ссылка на задачу (`S-N-NNN`) или KI в footer.

## 3. PR

- Название: `<type>(<scope>): <краткое описание> (S-N-NNN)`.
- В описании — ссылка на задачу и отчёт спринта.
- **CI должен быть зелёным.** Локальные прогоны не заменяют CI.
- Ревьюер проверяет чек-лист `AGENTS.md` §5 (Definition of Done).

## 4. Что проверяется автоматически

| Проверка | Команда |
|---|---|
| Backend линт | `ruff check backend/app backend/tests` |
| Backend типы | `mypy backend/app` |
| Backend тесты | `pytest -q` |
| Frontend типы | `pnpm --dir frontend typecheck` |
| Frontend линт | `pnpm --dir frontend lint` |
| Frontend тесты | `pnpm --dir frontend test` |
| Frontend сборка | `pnpm --dir frontend build` |

## 5. Запрещено

- Коммитить `.env`, ключи, токены.
- Использовать `--no-verify` (pre-commit хуки обязательны).
- Смешивать несвязанные изменения в одном PR.
- Нарушать read-only политику (см. `AGENTS.md` §4).