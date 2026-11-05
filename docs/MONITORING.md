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

## 2. Метрики (Prometheus, `/api/v1/metrics`)

| Метрика | Тип | Что показывает |
|---------|-----|----------------|
| `iiruchating_fetch_duration_seconds` | Histogram | Время `git fetch --all --prune` на репозиторий |
| `iiruchating_status_duration_seconds` | Histogram | Время сбора локального статуса (fast check + pygit2) |
| `iiruchating_repositories_total{state=...}` | Gauge | Текущее число репозиториев в каждом каноническом состоянии (обновляется при scrape из БД) |
| `iiruchating_scan_duration_seconds` | Gauge | Длительность последнего полного сканирования |
| `iiruchating_mirror_status_total{status=...}` | Gauge | Текущее число репозиториев по `mirror_status` (при scrape из БД) |
| `iiruchating_mirror_check_duration_seconds` | Histogram | Время проверки зеркала GitHub ↔ GitFlic |

Гистограммы **без лейбла `repo`** — чтобы не плодить кардинальность; разбор
медленных репозиториев идёт через JSON-лог `status_slow`.

```
# HELP iiruchating_repositories_total  Current number of repositories by canonical state
# TYPE iiruchating_repositories_total gauge
iiruchating_repositories_total{state="current"} 12
iiruchating_repositories_total{state="dirty"} 3
iiruchating_repositories_total{state="diverged"} 1

# HELP iiruchating_scan_duration_seconds  Duration of the last full discovery scan
# TYPE iiruchating_scan_duration_seconds gauge
iiruchating_scan_duration_seconds 2.4
```

`/api/v1/metrics` — **local-only**, без авторизации (как `/health`);
не публиковать наружу.

---

## 3. Логи (structlog, JSON)

События, которые нужно логировать:

| Событие | Поля | Зачем |
|---------|------|-------|
| `fetch_started` | `path`, `remote` | Трассировка (зарезервировано) |
| `fetch_completed` | `path`, `duration_ms` | Успешный fetch |
| `fetch_failed` | `path`, `remote_url`, `error`, `duration_ms` | Разбор инцидентов |
| `fetch_timed_out` | `path`, `remote_url`, `timeout_seconds`, `message` | Таймаут fetch, подсказка увеличить `FETCH_TIMEOUT` |
| `status_slow` | `repository_id`, `path`, `duration_ms` | Статус дольше 1 с |
| `scan_completed` | `roots`, `found`, `added`, `skipped`, `duration_ms` | Понимание покрытия и скорости |
| `action_executed` | `repo`, `action`, `actor` | Аудит мутаций (v0.2.0) |

Формат — JSON (`app/logging.py`), чтобы фильтровать `jq` без парсинга глазами.

---

## 4. Health endpoint

`GET /api/v1/health` возвращает:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "git_version": "git version 2.55.0.windows.5",
  "scan_roots": ["C:/Projects"],
  "db_ok": true,
  "providers": {
    "github": "not_configured",
    "gitflic": "not_configured"
  }
}
```

`status = degraded`, если `db_ok = false`. `providers` пока заглушки;
реальная проверка токенов — Спринт 9 (mirror).

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