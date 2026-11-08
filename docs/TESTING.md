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

## 5. E2E (frontend, Playwright)

Структура:

```
frontend/
  playwright.config.ts     # dev-сервер 5173, Chromium, ru-RU, trace/video on failure
  e2e/
    mock-api.ts            # единый page.route('**/api/v1/**') с изменяемым состоянием
    onboarding.spec.ts     # пустой дашборд -> «Сканировать» -> строка репозитория
    settings.spec.ts       # RU -> EN, светлая -> тёмная тема
    ai-commit.spec.ts      # dirty-репозиторий -> мок-LLM -> сообщение в модалке
```

Правила:

- **E2E не ходит в сеть и не трогает реальные репозитории.** Backend, БД и LLM
  заменены обработчиком `page.route()`; `POST /scan` меняет состояние мока, а
  `POST /repositories/{id}/ai/commit-message` возвращает детерминированный ответ.
- Тесты запускаются против Vite dev-сервера (`pnpm dev --port 5173`), Playwright
  сам поднимает и останавливает его через `webServer`.
- Локаль браузера — `ru-RU`: стартовый язык приложения предсказуем, а сценарий
  переключения на EN проверяет реальную смену словаря.
- При изменении API-контрактов обновляйте `e2e/mock-api.ts` вместе с
  `src/api/client.ts`.
- Команды: `pnpm --dir frontend test:e2e`, `test:e2e:ui`, `test:e2e:report`.
  Первый запуск: `pnpm --dir frontend exec playwright install chromium`.

## 6. RAG (code search)

- Unit-тесты (`backend/tests/test_code_search.py`) проверяют file walker,
  ignore-лист, чанкинг с перекрытием, hash, маскирование секретов и деградацию
  на SQLite (`503 rag_unavailable`).
- Реальный pgvector-поиск требует PostgreSQL с расширением `vector` и
  `POSTGRES_TEST_URL`; без него интеграционные проверки пропускаются.
- Индексация только читает файлы: `.git`, индекс Git и рабочие файлы не
  меняются. `.env`, ключи и lock-файлы не индексируются.