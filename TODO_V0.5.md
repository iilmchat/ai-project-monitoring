# TODO v0.5.0 — Dark Charts, Docker & Dependencies

**Текущая версия:** v0.4.0 (2026-11-05)
**Планируемая версия:** v0.5.0 «Insights & Integrations»
**Статус:** 🚧 В разработке (Sprint 24 завершён)
**Последнее обновление:** 2026-11-06

---

## 1. Цели v0.5.0

| # | Цель | Критерий достижения |
|---|------|---------------------|
| G1 | Графики выглядят частью продукта в обеих темах | recharts использует M3-токены для осей, сетки, тултипов и легенд; контраст ≥ 4.5:1 |
| G2 | Видеть runtime-состояние проекта, а не только Git | В карточке репозитория — контейнер, статус, health и опубликованные порты |
| G3 | Контролировать долг зависимостей | Список устаревших Python- и Node-пакетов с текущей и последней версией |
| G4 | Не упираться в rate-limit реестров | TTL-кэш 24 ч, ограничение concurrency, backoff, partial results |
| G5 | Сохранить read-only политику | Docker — только `GET`; манифесты только читаются; `pip`/`npm` не запускаются |
| G6 | Предсказуемый релиз | DoD каждого спринта, тесты, docs-consistency audit, тег `v0.5.0` |

---

## 2. Принципы

1. **Маленькие итерации:** спринт = законченная порция, `main` всегда зелёный.
2. **Read-only по умолчанию:** Docker-интеграция не управляет контейнерами; зависимости не обновляются автоматически.
3. **Один факт — один источник:** SPEC — контракты, ARCHITECTURE — устройство, этот файл — план.
4. **Деградация без падения:** недоступный Docker/реестр — это состояние (`unavailable`), а не 500.
5. **Кэш — часть контракта:** TTL и ключи кэша фиксируются в SPEC/ARCHITECTURE, а не «где-то в коде».
6. **Никаких новых зависимостей без ADR:** для v0.5.0 используем уже зафиксированный `httpx`; сравнение версий — собственное, без `packaging`/`semver`-библиотек.
7. **A11y и тема — в DoD:** новые блоки проверяются в light/dark и с клавиатуры.

---

## 3. Спринты

### Спринт 23 — Планирование v0.5.0 (✅ Завершён)

- [x] **S23-001:** создать `TODO_V0.5.md` с декомпозицией спринтов 24–26.
- [x] **S23-002:** обновить `docs/SPEC.md` (§3.14–3.15, §4, §5, §6, §8, §9),
  `docs/ARCHITECTURE.md` (§1–2, §8–12), `docs/KNOWN_ISSUES.md` (KI-009/010),
  `README.md` (Roadmap), `TODO.md` (актуальный этап и матрица KI).
- [x] **S23-003:** зафиксировать DoD каждого спринта и сверить контракты
  эндпоинтов со SPEC/ARCHITECTURE.

**DoD:** документы согласованы между собой; код приложения не менялся; план
содержит измеримые критерии и явные границы scope.

---

### Спринт 24 — Dark Charts & Docker Integration

**Статус:** ✅ Завершён (2026-11-06)

**Задачи**

- **S24-001. M3-палитра для recharts.**
  - Семантические chart-токены (`surface`, `on-surface`, `grid`, `tooltip-*`,
    `series-*`) в `DashboardCharts.tsx`; источник темы — `useTheme().resolved`.
  - Оси, `CartesianGrid`, `Legend`, `Tooltip` и текст тултипа берут цвета из
    токенов; данные (Pie/Bar) остаются брендовыми (primary/tertiary/success/error).
  - Семантические цвета состояний сохранить (`current` — emerald, `dirty` —
    amber, `ahead` — violet, `behind` — orange, `diverged`/`error` — red,
    `no_upstream`/`detached` — neutral).
  - Проверить light/dark, контраст WCAG AA, пустые состояния и `prefers-reduced-motion`.
  - Тесты: маппинг серий, переключение темы без перезагрузки.

- **S24-002. DockerService и read-only Docker SDK.**
  - `app/services/docker_service.py`: `docker` SDK, matcher (bind mounts +
    compose labels), нормализация контейнеров, доменные ошибки.
  - `DockerService.get_container_status(repo_path, refresh=False)`:
    `status ∈ {running, stopped, not_found, unavailable}`; кэш
    `DOCKER_STATUS_TTL_SECONDS=30`; таймаут 3 с; ошибки → `unavailable`, не 5xx.
  - API `GET /api/v1/repositories/{id}/docker` + Pydantic-схемы.
  - Сопоставление: bind-mount `Source`/`Destination` с `DOCKER_PATH_MAP`
    host→container → `com.docker.compose.project.working_dir` → `...project` →
    имя контейнера/образа; в ответе — `match`, чтобы UI мог показать уверенность.
  - SDK вызывает только `ping()` и `containers.list(all=True)`; никаких
    start/stop/restart/exec/logs.
  - Тесты: fake Docker client, running/stopped/not_found/unavailable, path mapping,
    cache/refresh; опциональный smoke-тест при доступном Docker.

- **S24-003. DooD и конфигурация.**
  - `docker-compose.yml`: монтирование `/var/run/docker.sock:ro` и переменные
    `DOCKER_ENABLED`, `DOCKER_HOST`, `DOCKER_PATH_MAP`,
    `DOCKER_STATUS_TTL_SECONDS`, `DOCKER_TIMEOUT_SECONDS`; `PROJECTS_ROOT` для
    host-root.
  - `backend/Dockerfile`: Docker SDK ставится из `requirements.txt`, Docker CLI
    не нужен.
  - `.env.example`, `docs/GETTING_STARTED.md` — настройка Docker и Windows-ограничения.
  - Проверка DooD: `GET /repositories/{id}/docker` работает из backend-контейнера
    через смонтированный сокет.

- **S24-004. UI Docker, тесты и документация.**
  - `frontend/src/api/types.ts`: `DockerStatus`, `DockerContainer`, `DockerPort`;
    `api/client.ts`: `getDockerStatus`.
  - Бейдж `running / stopped / not_found / unavailable`, health, image,
    compose service, опубликованные порты.
  - Для `status=unavailable` — понятное состояние «Docker недоступен» + причина
    (KI-009), без падения карточки.
  - Ленивая загрузка при раскрытии карточки/деталей; кнопка «Обновить» дергает
    `?refresh=true`; управляющих кнопок контейнера нет.
  - Тесты: fake Docker client, API-контракт, path mapping, cache/refresh; UI-тесты.
  - ADR-0007 «Read-only Docker integration via the Python Docker SDK»;
    SPEC/ARCHITECTURE/CHANGELOG/RELEASES/KNOWN_ISSUES.

**DoD:**

- [x] Графики читаемы в light/dark, контраст AA, hex-литералы только в token maps.
- [x] `GET /repositories/{id}/docker` возвращает `DockerStatus` по SPEC §3.14;
      running/stopped/not_found/unavailable различаются.
- [x] Docker-ошибки не дают 5xx; таймаут ≤ 3 с; кэш 30 с; `refresh=true` работает.
- [x] В коде нет вызовов start/stop/restart/exec/logs (проверено grep-аудитом).
- [x] На Windows без сокета SDK использует npipe либо возвращает `unavailable`
      (KI-009), карточка не ломается.
- [x] Тесты backend/frontend зелёные; `ruff`, `mypy --strict`, `pnpm` — зелёные.
- [x] Документация и ADR-0007 обновлены; секретов в диффе нет.

---

### Спринт 25 — Dependency Management (Python)

**Статус:** ⬜ Запланирован

**Задачи**

- **S25-001. Кэш и модель `dependency_cache`.**
  - Таблица `dependency_cache(key*, ecosystem, package, latest_version, etag,
    payload, checked_at)` + Alembic-миграция.
  - TTL `DEPENDENCY_CACHE_TTL_SECONDS=86400` (24 ч); ключ `pypi:<normalized-name>`.
  - Single-flight: параллельные запросы одного пакета не дублируют сетевой вызов.
  - Stale-while-revalidate: при ошибке реестра отдаём stale-кэш с пометкой
    `source=stale_cache`, если он есть.

- **S25-002. Парсер `requirements.txt`.**
  - Читать только файлы внутри корня репозитория; `-r` include — с защитой
    от path traversal и циклов, глубина ≤ 3. `-c`/constraints не раскрываются:
    они ограничивают версии, но не объявляют зависимости.
  - Поддержать: комментарии, пустые строки, `==`, `~=`, `>=`, `>`, `<=`, `<`,
    extras, environment markers, hashes, line continuation.
  - Классифицировать: `exact` (только `==`), `range` (остальные спецификаторы),
    `ignored` (`-e`, VCS, local path, URL).
  - Никаких вызовов `pip`/`pip index`; только чтение файла + registry HTTP.

- **S25-003. PyPI-клиент.**
  - `GET https://pypi.org/pypi/{name}/json` (timeout 5 с), User-Agent
    `IIRuchating/0.5`.
  - 404 → `not_found`/`unknown`; 429/5xx → backoff (0.5/1/2 с, максимум 3 попытки);
    ошибки не роняют весь отчёт.
  - Concurrency ≤ 4 (`DEPENDENCY_CHECK_CONCURRENCY`), последовательность
    детерминирована для тестов.

- **S25-004. API `GET /repositories/{id}/dependencies`.**
  - Параметры `refresh?: bool`, `ecosystem?: python|node`; по умолчанию — оба.
  - Ответ `DependencyReport` по SPEC §3.15; отсутствие манифеста — запись
    `status=no_manifest`, а не 404/500.
  - `refresh=true` обходит TTL только для этого репозитория и обновляет кэш.

- **S25-005. UI-блок Python-зависимостей.**
  - Счётчики `outdated / up_to_date / unknown / ignored`, раскрываемый список.
  - Бейджи `major / minor / patch`, ссылка на `pypi.org/project/<name>`, кнопка
    «Проверить снова» (`refresh=true`).
  - Ленивая загрузка; пустое состояние «requirements.txt не найден».
  - В карточке — компактный счётчик устаревших, без раскрытия всего списка.

- **S25-006. Тесты.**
  - Парсер: pinned/range/extras/markers/include/cycle/path traversal.
  - Сервис: cache hit/miss, TTL, single-flight, 429/backoff, 404, stale cache.
  - API: существующий/несуществующий репозиторий, `no_manifest`, `ecosystem=python`.
  - Frontend: счётчики, список, пустое состояние, refresh.

- **S25-007. Документация и ADR.**
  - ADR-0008 «Dependency checks without package-manager execution».
  - SPEC/ARCHITECTURE/KNOWN_ISSUES/.env.example/GETTING_STARTED/CHANGELOG/RELEASES.

**DoD:**

- [ ] `requirements.txt` парсится без выполнения `pip`; includes не выходят за
      корень репозитория.
- [ ] `==` даёт точное сравнение; range показывает нижнюю границу и не выдаёт
      ложный «outdated» за пределами выбранной семантики.
- [ ] Кэш 24 ч переживает перезапуск; повторный запрос не ходит в PyPI.
- [ ] 429/5xx дают `unavailable`/`stale_cache` и HTTP 200, без падения отчёта.
- [ ] `GET /repositories/{id}/dependencies` соответствует SPEC §3.15.
- [ ] UI показывает счётчики и список; пустое состояние и ошибки читаемы.
- [ ] Тесты, `ruff`, `mypy --strict`, frontend-проверки — зелёные.
- [ ] Документация и ADR-0008 обновлены.

---

### Спринт 26 — Dependency Management (Node) & Релиз v0.5.0

**Статус:** ⬜ Запланирован

**Задачи**

- **S26-001. Парсер `package.json`.**
  - `dependencies` + `devDependencies`; `optionalDependencies` — вторая волна,
    если останется время (не блокирует DoD).
  - Scoped-пакеты (`@scope/name`), `workspace:*`, `file:`, `link:`, `git+`,
    `http(s):`, `npm:` aliases — `ignored`.
  - `1.2.3` → `exact`; `^`, `~`, `>=`, `*`, `latest` → `range`/`unknown`
    (нижняя граница, если парсится).
  - Не читать `node_modules`; не запускать `npm`/`pnpm`.

- **S26-002. npm registry client.**
  - `GET https://registry.npmjs.org/{name}/latest`; scoped-name URL-encode
    (`@scope%2Fname`).
  - 404 → `unknown`; 429/5xx → backoff; timeout 5 с; concurrency ≤ 4.
  - Кэш `npm:<name>`, TTL 24 ч, та же таблица `dependency_cache`.

- **S26-003. Объединённый отчёт и UI.**
  - По умолчанию `GET /repositories/{id}/dependencies` возвращает оба ecosystem;
    отсутствующий манифест — запись `status=no_manifest`. `ecosystem=node` — только Node.
  - Сортировка: `major` → `minor` → `patch`, затем имя; счётчик устаревших в
    карточке репозитория (Python + Node вместе).
  - Partial failure: недоступный npm не скрывает Python-блок и наоборот.
  - Обновить column manager: опциональные колонки «Docker» и «Зависимости».

- **S26-004. Финальный аудит и релиз v0.5.0.**
  - Версии `0.5.0` (backend `app_version`, frontend `package.json`), CHANGELOG,
    RELEASES, README, SPEC, TODO_V0.5.
  - `docs/prompts/docs-consistency-audit.md`: SPEC ↔ ARCHITECTURE ↔ README ↔ KI.
  - Финальные проверки: `ruff`, `mypy --strict`, `pytest -q`,
    `pnpm typecheck && lint && test && build`, Docker Compose smoke.
  - Тег `v0.5.0` в GitHub и GitFlic; `SHA(main)` совпадает; GitHub Release.

**DoD:**

- [ ] `package.json` парсится; scoped/ignored/ranges классифицируются корректно.
- [ ] npm-клиент кэширует ответы, обрабатывает 404/429/5xx и timeout.
- [ ] Объединённый отчёт не теряет второй ecosystem при partial failure.
- [ ] Счётчик устаревших и список видны в карточке/деталях; колонки управляемы.
- [ ] Все проверки зелёные; docs-consistency audit пройден.
- [ ] Тег `v0.5.0` есть в обоих провайдерах, `SHA(main)` совпадает.
- [ ] CHANGELOG/RELEASES/README/SPEC отражают фактическое поведение.

---

## 4. Контракты v0.5.0 (сверка со SPEC/ARCHITECTURE)

| Контракт | Источник истины |
|----------|-----------------|
| `GET /repositories/{id}/docker`, `DockerStatus`, коды ошибок | `docs/SPEC.md` §3.14 |
| `GET /repositories/{id}/dependencies`, `DependencyReport`, статусы | `docs/SPEC.md` §3.15 |
| Таблица `dependency_cache`, TTL 24 ч | `docs/SPEC.md` §4, §5; `docs/ARCHITECTURE.md` §11 |
| Docker SDK, UDS/npipe, `DOCKER_PATH_MAP`, безопасность | `docs/ARCHITECTURE.md` §10; `docs/adr/0007-docker-integration.md` |
| Docker/Windows-ограничения | `docs/KNOWN_ISSUES.md` KI-009 |
| Rate-limit PyPI/npm и кэш | `docs/KNOWN_ISSUES.md` KI-010 |
| Chart-токены и темы | `docs/SPEC.md` §9.8; `docs/ARCHITECTURE.md` §9.5 |
| Docker/зависимости в UI | `docs/SPEC.md` §9.9; `docs/ARCHITECTURE.md` §9.6 |

---

## 5. Сквозной Definition of Done

- [ ] Все задачи спринта `[x]` или явно перенесены в `KNOWN_ISSUES` с `KI-NNN`.
- [ ] `ruff check backend/app backend/tests` — 0.
- [ ] `mypy backend/app` — 0.
- [ ] `pytest -q` — passed (покрытие ≥ 70% для новых сервисов).
- [ ] `pnpm --dir frontend typecheck && pnpm --dir frontend lint && pnpm --dir frontend test` — 0.
- [ ] `pnpm --dir frontend build` — 0; entry bundle ≤ 100 kB gzip, новые блоки lazy.
- [ ] Новые контракты отражены в SPEC; устройство — в ARCHITECTURE.
- [ ] Read-only: нет start/stop/restart/exec/logs; `pip`/`npm` не вызываются;
      destructive-команды отсутствуют (grep-аудит).
- [ ] `docs/RELEASES.md` — отчёт по спринту; `docs/CHANGELOG.md [Unreleased]` обновлён.
- [ ] Нет секретов в диффе; токены только маскируются.
- [ ] Для релизного спринта — docs-consistency audit и тег в обоих провайдерах.

---

## 6. Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Docker socket/npipe требует прав/настройки на Windows | Высокая | Среднее | KI-009: SDK npipe, `status=unavailable`, инструкция в GETTING_STARTED |
| Docker socket = root-эквивалент | Средняя | Высокое | local-only, только `GET`, opt-in mount, `DOCKER_ENABLED=false`, не проксировать API наружу |
| Разные path namespace (host vs container) | Высокая | Среднее | `DOCKER_PATH_MAP`, fallback на compose project/имя, поле `match` |
| Ложное сопоставление контейнеров | Средняя | Среднее | compose-labels приоритетнее имени; поле `match`; никаких действий с контейнерами |
| Rate-limit PyPI/npm | Высокая | Среднее | KI-010: 24 ч кэш, concurrency 4, backoff, partial results |
| Разнообразие манифестов (extras, markers, workspace, aliases) | Высокая | Среднее | явные `kind/status`, `ignored`, тесты на фикстурах, без ложных «outdated» |
| Сравнение диапазонов версий даёт ложные срабатывания | Средняя | Среднее | `range` + нижняя граница + severity; точное сравнение только для `exact` |
| Рост bundle из-за новых блоков | Средняя | Среднее | lazy-загрузка, бюджет 100 kB gzip |
| Контраст графиков в тёмной теме | Средняя | Среднее | семантические токены, проверка AA, тест переключения темы |
| Кэш зависимостей устаревает | Низкая | Низкое | `refresh=true`, `checked_at` в ответе, stale-пометка |

---

## 7. Вне scope v0.5.0

- Управление контейнерами: start/stop/restart/pause, `exec`, просмотр логов,
  `docker compose up/down`, удаление образов/volume.
- Обновление зависимостей: `pip install -U`, `npm update`, редактирование
  манифестов, lock-файлы, транзитивные зависимости.
- Аудит уязвимостей (CVE) и лицензионная проверка пакетов.
- Приватные registry/аутентификация (PyPI private index, npm private registry).
- Docker Swarm, Kubernetes, удалённые Docker-хосты (кроме `DOCKER_HOST` для
  локального сокета).
- Синхронизация Saved Views в БД и история статусов — v0.6.0+ (`TODO.md`).
