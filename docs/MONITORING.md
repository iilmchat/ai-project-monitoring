# MONITORING — что и как мониторить в IIRuchating

Документ фиксирует **best practices observability** для локального Git-дашборда.
Основан на SRE-подходе к Git (Git Reliability Engineering): версионный
контроль — критичная система, к ней применимы SLO, метрики и алерты[reference:5].

---

## 1. SLI / SLO (что измеряем)

| SLI | Что | SLO (цель) |
|-----|-----|------------|
| `fetch` latency | Время `git fetch --all --prune` | p95 < 2 с (локально) |
| `status` latency | Время `pygit2.status()` | p95 < 200 мс на репо |
| `fetch` success rate | Доля успешных fetch | > 98% |
| `scan` latency | Время полного сканирования | p95 < 5 с на 20 репо |
| Conflict rate | Доля репозиториев в `diverged` | < 5% (error budget)[reference:6] |

Если SLO нарушен — это сигнал, а не «повод паниковать»; error budget
позволяет принимать решения: инвестировать в оптимизацию или принять риск.

---

## 2. Метрики (Prometheus, `/metrics`)

```
# HELP iiruchating_fetch_duration_seconds  Fetch duration per repository
# TYPE iiruchating_fetch_duration_seconds histogram
iiruchating_fetch_duration_seconds_bucket{repo="...",le="1"} ...

# HELP iiruchating_status_duration_seconds  Status duration per repository
# TYPE iiruchating_status_duration_seconds histogram

# HELP iiruchating_repositories_total  Repositories by state
# TYPE iiruchating_repositories_total gauge
iiruchating_repositories_total{state="current"} 12
iiruchating_repositories_total{state="dirty"} 3
iiruchating_repositories_total{state="diverged"} 1

# HELP iiruchating_scan_duration_seconds  Full scan duration
# TYPE iiruchating_scan_duration_seconds gauge
iiruchating_scan_duration_seconds 2.4
```

`/metrics` — **local-only**, не публиковать наружу (как `/metrics` в
`ai-teacher_python`, nginx отдаёт 404).

---

## 3. Логи (structlog, JSON)

События, которые нужно логировать:

| Событие | Поля | Зачем |
|---------|------|-------|
| `fetch_started` | `repo`, `remote` | Трассировка |
| `fetch_failed` | `repo`, `error`, `duration` | Разбор инцидентов |
| `status_slow` | `repo`, `duration_ms` | Деградация производительности |
| `scan_completed` | `roots`, `found`, `duration` | Понимание покрытия |
| `action_executed` | `repo`, `action`, `actor` | Аудит мутаций |

Формат — JSON, чтобы можно было фильтровать `jq` без парсинга глазами.

---

## 4. Health endpoint

`GET /health` возвращает:

```json
{
  "status": "ok",
  "version": "0.2.0",
  "git_version": "2.45.1",
  "scan_roots": ["/home/user/projects"],
  "db_ok": true,
  "uptime_seconds": 3600
}
```

Не путать с `/metrics`: health — для «жив ли процесс», metrics — для
«как он работает».

---

## 5. Алерты (что настроить, когда будет Prometheus)

- `fetch_duration_seconds` p95 > 5 с за 10 минут → «fetch деградировал».
- `status_duration_seconds` p95 > 500 мс → «status стал медленным».
- `fetch_success_rate` < 95% → «проблемы с remote».
- `repositories_total{state="diverged"}` вырос на 3 за день → «накопились
  конфликты».

Пока Prometheus нет — те же пороги можно проверять cron-скриптом и писать в
лог `alert_triggered`.

---

## 6. Что НЕ делать

- Не тащить ELK/Prometheus-сервер в v0.2.0: для локального инструмента
  достаточно `/metrics` + JSON-логов.
- Не измерять всё подряд: 5–7 метрик, которые реально помогают принимать
  решения.
- Не логировать содержимое файлов и diff'ы (PII/секреты).