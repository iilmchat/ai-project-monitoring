# ADR-0007: Read-only Docker integration via the Python Docker SDK

**Статус:** Accepted
**Дата:** 2026-11-06
**Контекст:** Sprint 24 (S24-002), SPEC §3.14, ARCHITECTURE §10

## Контекст

Нужно показывать в карточке репозитория, запущен ли его контейнер, на каком
порту и в каком состоянии. Управление контейнерами не требуется: только
чтение. Backend работает в Docker (DooD), поэтому доступ к демону хоста идёт
через смонтированный `/var/run/docker.sock`. На Windows при локальном запуске
Docker Desktop использует named pipe `\\.\pipe\docker_engine`.

Рассматривались три варианта:

| Вариант | Плюсы | Минусы |
|---|---|---|
| A. `docker` Python SDK | Готовый Docker API, `Mounts`/`Labels`/`Ports`, support UDS и npipe, `DockerException` | Новая Python-зависимость; синхронный API |
| B. `docker ps` / `docker inspect` subprocess | Нет Python-зависимости | Нужно ставить Docker CLI в образ; ручной JSON-парсинг; хуже тестируется |
| C. Сырой Docker Engine API через `httpx` | Нет новой зависимости | Нужно вручную реализовывать UDS/npipe, версии API, ошибки |

## Решение

**Вариант A — `docker` SDK (`docker==7.1.0`).**

- SDK вызывает только `ping()` и `containers.list(all=True)`; lifecycle-операции
  (`start`, `stop`, `restart`, `exec`, logs) отсутствуют.
- Синхронные вызовы выполняются в `asyncio.to_thread`, чтобы не блокировать
  event loop.
- Подключение: `DOCKER_HOST` (в compose — `unix:///var/run/docker.sock`), иначе
  `docker.from_env()` выбирает UDS/npipe по платформе.
- `DOCKER_PATH_MAP` переводит host-пути из `com.docker.compose.project.working_dir`
  и bind-mount `Source` в namespace backend-контейнера.
- Ошибки (`DockerException`, connection errors) превращаются в
  `status="unavailable"` и строку `error`; HTTP 500 не возвращается.
- В Docker-образе Docker CLI не нужен: SDK устанавливается из
  `requirements.txt`.

## Последствия

- Появляется одна runtime-зависимость (`docker` + транзитивные `requests`,
  `urllib3`); она зафиксирована в `requirements.txt`.
- Тесты используют fake Docker client, реальный демон не требуется; опциональный
  smoke-тест возможен при доступном Docker.
- `:ro` на bind-mount сокета не делает Docker API read-only — сокет остаётся
  root-эквивалентом. Поэтому приложение ограничено `GET`-операциями, а
  `DOCKER_ENABLED=false` остаётся аварийным выключателем.
- Если Docker Desktop/npipe недоступен, UI показывает `Docker not available`,
  а не падает (см. KI-009).
