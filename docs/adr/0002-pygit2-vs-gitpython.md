# ADR-0002: pygit2 для status/discovery, shell/GitPython для fetch/compare

**Статус:** Accepted
**Дата:** 2026-11-05
**Контекст:** S2-001 (Git-абстракция), KI-002 (производительность `status()`)

## Контекст

Проект сканирует десятки локальных репозиториев и для каждого вычисляет
`dirty`-состояние и `ahead/behind`. Два подхода:

- **GitPython / shell** — запускает `git status` как subprocess на каждый
  репозиторий.
- **pygit2** — биндинги к libgit2, работает in-process.

При 20+ репозиториях и кэше статуса 60 с subprocess-подход даёт заметный
оверхед на spawn процесса, а парсинг человекочитаемого вывода `git status`
хрупок к локали и версии Git.

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| A. Только GitPython | Знакомый API, гибкость | subprocess на каждый вызов, ~11 мс/репо, парсинг вывода |
| B. Только pygit2 | Быстро (~2 мс/репо), без spawn | Нет high-level `fetch`/`compare`, нужен libgit2 |
| C. Гибрид: pygit2 для status/discovery + shell для fetch/compare | Быстрый status, гибкий fetch | Два бэкенда, нужно тестировать оба |

## Решение

Выбран **вариант C**:

- `pygit2.Repository(path).status()` — для `dirty`, `staged`, `untracked`,
  `conflicted`, `detached`, upstream.
- `git fetch --all --prune` и `git rev-list --left-right --count` — через
  subprocess с таймаутом (или GitPython, где удобнее).

`fetch` и `compare` — редкие операции (по кнопке «Обновить» или при явном
запросе), поэтому subprocess-оверхед там приемлем. `status` — частая операция
(дашборд), поэтому pygit2.

## Последствия

- Дашборд остаётся отзывчивым при 20+ репозиториях.
- Нужно документировать две ветки кода и тестировать обе.
- При проблемах с libgit2 (KI-002) — fallback на `git status --porcelain -uno`
  для быстрого «грязный/чистый».