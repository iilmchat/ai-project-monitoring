# CHANGELOG — История версий

## [Unreleased]

—

## [0.1.0] — 2026-11-05

Первый MVP: сканирование, локальный статус, сравнение с удалённым, дашборд, read-only.

### Добавлено

- **Discovery:** рекурсивный поиск `.git/` в `SCAN_ROOTS` с `SCAN_DEPTH` и `SCAN_IGNORE`; параллельное сканирование (`SCAN_CONCURRENCY`); запись `scan_runs`.
- **Git-абстракция:** `pygit2` для `status()` и discovery; shell/GitPython для `fetch` и `compare`; таймауты и обработка ошибок.
- **Канонический статус:** `current / behind / ahead / diverged / dirty / no_upstream / detached / error`; `ahead/behind` только после `fetch`.
- **API:** `/scan`, `/repositories`, `/repositories/{id}/status`, `/compare`, `/dashboard`, `/recommendations`; track/untrack.
- **Remote Comparator:** `git fetch --all --prune` + `rev-list --left-right --count`; опционально GitHub Compare API.
- **Рекомендации:** генерация команд на основе состояния (без выполнения).
- **Frontend:** дашборд со сводкой, фильтры, секция «Не отслеживаются», детали репозитория, кнопка «Обновить».
- **Docker:** `docker-compose.yml`; SQLite-volume.
- **Тесты:** ~80 backend (реальные tmp-репозитории), ~30 frontend.

### Ограничения

- Мутации (`pull`/`push`) не реализованы — только рекомендации.
- GitFlic Compare API не поддержан в v0.1 (локальное сравнение работает).
- История статусов не ведётся (только последний снимок).