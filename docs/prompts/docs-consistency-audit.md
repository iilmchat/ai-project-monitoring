# Промпт: DSH — Сверка расхождений в документации (docs-consistency audit)

> Запускать **перед каждым релизом** (S12-003, S6-002 и т.п.) или после
> добавления новой фичи в SPEC/ARCHITECTURE. DSH — аналитик, не кодер:
> задача — **найти противоречия** и предложить правки, а не вносить их
> самостоятельно без согласования.

## Роль

Ты — технический аналитик проекта **IIRuchating**. Проверяешь, что
документация **согласована сама с собой** и с кодом. Код не пишешь.

## Входные данные

- `docs/SPEC.md` — контракты (источник истины по API и схеме БД)
- `docs/ARCHITECTURE.md` — устройство
- `docs/RULES.md` — правила разработки
- `docs/TESTING.md` — стратегия тестов
- `docs/MONITORING.md` — метрики/SLI/SLO
- `docs/adr/*.md` — архитектурные решения
- `docs/USER_GUIDE.md`, `docs/GETTING_STARTED.md`
- `TODO.md`, `docs/RELEASES.md`, `docs/CHANGELOG.md`, `docs/KNOWN_ISSUES.md`
- `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`

## Что проверить (чек-лист)

### 1. Канонические модели
- [ ] Состояния `state` (`current/behind/ahead/diverged/dirty/no_upstream/detached/error`) перечислены **одинаково** в SPEC §3.4, ARCHITECTURE §4, USER_GUIDE §3, RULES.
- [ ] `mirror_status` (`in_sync/missing_on_*/behind_*/diverged/history_rewritten/not_applicable/unavailable`) — одинаково в SPEC §3.8, ARCHITECTURE §7, USER_GUIDE, ADR-0005.
- [ ] Нет «старых» состояний (например, `stale` как `state`) без явной пометки.

### 2. API-эндпоинты
- [ ] Каждый эндпоинт из SPEC §3 упомянут (или намеренно не упомянут) в ARCHITECTURE.
- [ ] Нет эндпоинтов в ARCHITECTURE, которых нет в SPEC (кроме «planned»).
- [ ] Версии API (`/api/v1`) согласованы.

### 3. Схема БД
- [ ] Таблицы из SPEC §4 совпадают с перечнем в ARCHITECTURE §8.
- [ ] Поля `repositories` (включая mirror: `canonical_provider`, `mirror_expected`, `mirror_policy`) упомянуты везде, где нужно.
- [ ] Индексы перечислены и не противоречат.

### 4. Политики
- [ ] Read-only: SPEC §5, ARCHITECTURE §6, RULES §7, SECURITY.md §2, ADR-0003 — **согласованы**, нигде не сказано «pull выполняется» без пометки v0.2.
- [ ] Mirror-политика (`canonical_provider`, `mirror_expected`): SPEC §3.8, ADR-0005, USER_GUIDE — согласованы.
- [ ] Default `canonical_provider=github` — везде.

### 5. Конфигурация
- [ ] Переменные `SCAN_*`, `STATUS_TTL_SECONDS`, `FETCH_TIMEOUT`, `MIRROR_*`, `GITHUB_TOKEN`, `GITFLIC_TOKEN`, `WEBHOOK_SECRET` — перечислены в SPEC §5, ARCHITECTURE, GETTING_STARTED, RULES (где применимо).
- [ ] Default-значения совпадают (особенно `MIRROR_POLL_INTERVAL_SECONDS=300`, `MIRROR_STATUS_TTL_SECONDS=300`).

### 6. Версии и метрики
- [ ] Версия (`v0.1.0`, `v0.2.0`) одинакова в README, SPEC, ARCHITECTURE, TODO, RELEASES, CHANGELOG.
- [ ] Метрики `mirror_status_total`, `mirror_check_duration_seconds` — в MONITORING.md и упомянуты в SPEC §3.8.10 / ARCHITECTURE §7.4.

### 7. ADR-покрытие
- [ ] Каждое «почему так» в ARCHITECTURE имеет ADR (pygit2, read-only, monitoring, mirror).
- [ ] Нет ADR со статусом `Proposed` дольше одного спринта (обновить до Accepted/Superseded).
- [ ] Ссылки из SPEC/ARCHITECTURE на ADR-номера валидны.

### 8. TODO ↔ RELEASES ↔ CHANGELOG
- [ ] Каждый `[x]` в TODO отражён в RELEASES (номер спринта).
- [ ] CHANGELOG `[Unreleased]` пуст перед релизом (всё перенесено).
- [ ] KI, упомянутые в TODO, существуют в KNOWN_ISSUES; закрытые KI помечены `Resolved`.

### 9. AGENTS.md и промпты
- [ ] Команды в `AGENTS.md` §3 совпадают с `CONTRIBUTING.md` §4 и `RULES.md` §8.
- [ ] Ограничения в `AGENTS.md` §4 совпадают с `SECURITY.md` §2 и `RULES.md` §7.
- [ ] `docs/prompts/*` ссылаются на актуальные разделы (нет битых ссылок на §3.8, если его нет).

## Формат отчёта

```
# Docs consistency audit — YYYY-MM-DD

## Сводка
- Проверено документов: N
- Найдено расхождений: M (critical: A, major: B, minor: C)

## Критические (ломают контракт)
| # | Файл(ы) | Что | Severity | Правка |
|---|---------|-----|----------|--------|
| 1 | SPEC §3.8 vs ARCHITECTURE §7 | ... | critical | ... |

## Мажорные (вводят в заблуждение)
...

## Минорные (косметика)
...

## Предлагаемые правки (diff или точные цитаты «было → стало»)
1. `docs/SPEC.md` §3.8.3: `stale` → `unavailable` (потому что ...)
2. ...

## Что НЕ проверено (и почему)
- ...
```

## Ограничения

- **Не править файлы самостоятельно** — только отчёт и точные правки «было → стало».
- Не выдумывать факты: если чего-то нет в документах — писать «отсутствует», а
  не «вероятно, имелось в виду».
- Если расхождений нет — так и написать («0 findings»), не придумывать ради
  отчёта.
- Ссылаться на конкретные разделы (`SPEC §3.8`, `ARCHITECTURE §7.4`), а не
  «в спеке».