# ADR-0020: SAST policy — tools, rules and limits

**Статус:** Accepted
**Дата:** 2026-11-11
**Контекст:** Спринт 59 (S59-001), v1.3.0

## Контекст

Нужно находить небезопасный код (`eval`, command injection, SQL-конкатенация)
в локальных репозиториях, не исполняя код проекта и не превращая проверку в
источник 500/таймаутов. В окружении может не быть bandit/semgrep/eslint.

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| Только bandit | Просто, Python | Нет JS/TS/C# |
| Только semgrep | Мультиязычность | Нужны правила/бинарник, сеть для registry |
| bandit + semgrep + eslint fallback | Покрывает Python и JS/TS, деградирует | Разные форматы вывода |
| SAST через внешний сервис | Нет локальных инструментов | Нарушает приватность и offline-first |

## Решение

- `bandit` добавлен в `requirements.txt` и ищется как бинарник или
  `python -m bandit`.
- `semgrep` — опциональный бинарник; запускается только с локальными правилами
  (`SAST_SEMGREP_CONFIG` или bundled `app/sast_rules/default.yml`),
  `--metrics=off`, `--disable-version-check`; `--config auto` и сеть запрещены.
- Если semgrep недоступен, используется локальный `node_modules/.bin/eslint`
  как fallback для JS/TS.
- Отсутствие инструмента → `tool.status=unavailable`, отчёт HTTP 200.
- Нормализация к общей шкале `critical|high|medium|low|unknown`, дедупликация
  по fingerprint, лимиты: timeout 120 с, вывод 8 MiB, 500 находок.
- Кэш `sast_cache` 24 ч по `repo_id + head_sha + dirty_hash + tools`;
  `refresh=true` обходит TTL. Недоступный результат не кэшируется.
- Только чтение: `GIT_OPTIONAL_LOCKS=0`, shell не используется, код проекта не
  исполняется.

## Последствия

- Python-проекты получают SAST «из коробки» после установки зависимостей;
  JS/TS — при наличии semgrep или локального eslint.
- Правила semgrep фиксированы и не обновляются из сети; это осознанный
  supply-chain trade-off.
- Нет автоисправлений: UI предлагает объяснение через LLM, изменения вносит
  человек.
- При необходимости расширить правила — добавить YAML в `app/sast_rules/` и
  обновить ADR.
