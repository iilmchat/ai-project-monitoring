# ADR-0004: Мониторинг и observability (best practices)

**Статус:** Proposed
**Дата:** 2026-11-05
**Контекст:** v0.2.0, спринт 4 (Monitoring)

## Контекст

Проект работает локально, но при 20+ репозиториях и регулярном `fetch`
важно понимать: не деградировал ли `status`, не «залипает» ли `fetch`, не
растёт ли число `diverged`. Без метрик мы узнаём о проблемах только по
ощущениям («дашборд стал тормозить»).

Best practices для Git reliability engineering (SRE-подход)[reference:0]:

- **SLO/SLI для Git-операций**: latency `fetch`, latency `status`, доля
  успешных `fetch`, время разрешения конфликтов.
- **Метрики репозитория**: размер, число объектов, частота коммитов,
  conflict rate.
- **Алерты**: `fetch` дольше N секунд, `status` дольше M мс, рост `diverged`
  за неделю.
- **Логи**: структурированные события `fetch_failed`, `status_slow`,
  `scan_completed`.

## Решение

В v0.2.0 добавить **лёгкий observability-слой**:

1. **Prometheus-метрики** (in-process, без внешнего сервера):
   - `iiruchating_fetch_duration_seconds{repo,status}`
   - `iiruchating_status_duration_seconds{repo}`
   - `iiruchating_repositories_total{state}`
   - `iiruchating_scan_duration_seconds`
2. **`/metrics`** — Prometheus text format, bind local-only (как в
   `ai-teacher_python`).
3. **Структурированные логи** (`structlog`): `fetch_started`,
   `fetch_failed`, `status_slow`, `scan_completed`.
4. **Health endpoint**: `/health` с `git_version`, `scan_roots`, `db_ok`.

Не тащить полноценный ELK/Prometheus-сервер: для локального инструмента
достаточно `/metrics` и JSON-логов, которые можно смотреть глазами или
подключить к `prometheus_client` при желании.

## Последствия

- Можно ответить на вопрос «почему дашборд тормозит» без профилировщика.
- Логи становятся машиночитаемыми.
- Нужно аккуратно сделать метрики «дешёвыми» (не сканировать всё на каждый
  scrape).