# TESTING — стратегия тестирования IIRuchating

## 1. Принцип: реальный Git, а не моки

Ключевая особенность проекта — работа с состояниями Git. Моки здесь **врут**.
Поэтому:

- Каждый тест статуса создаёт **временный репозиторий** (`tmp_path` + `git init`).
- Для `ahead/behind` — создаётся **bare-remote** (`git init --bare`) и два клона.
- `fetch` тестируется на локальном bare-repo, а не на сети.

## 2. Пирамида

| Уровень | Что тестируем | Инструмент |
|---|---|---|
| Unit | Классификация `state` по `(ahead, behind, dirty)` | pytest, чистые функции |
| Integration | Discovery + Status + API на tmp-репозиториях | pytest + httpx.AsyncClient |
| E2E (frontend) | Дашборд, фильтры, track/untrack | Playwright |

## 3. Обязательные сценарии (минимум)

- `current`: чистый репозиторий, всё запушено.
- `dirty`: modified + staged + untracked.
- `ahead`: локальный коммит без push.
- `behind`: bare-remote получил коммит, локальный — нет.
- `diverged`: и локальный, и удалённый коммиты.
- `no_upstream`: ветка без tracking.
- `detached`: checkout по SHA.
- `error`: битый `.git` или недоступный remote.

## 4. Покрытие

- Backend: ориентир ≥ 70%; в v0.1.0 покрытие не измерялось (`pytest-cov` не подключён).
- Frontend: ориентир ≥ 60%; в v0.1.0 покрытие не измерялось.
- Flaky-тест — блокер: завести KI и починить или `skip` с причиной.