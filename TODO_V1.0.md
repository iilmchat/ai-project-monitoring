# TODO v1.0.0 — Secure Desktop

**Статус:** Sprint 47–49 реализованы; v1.0.0 выпущен (Windows desktop).
**База:** v0.9.0 «Stability & RAG» (E2E, GigaChat, Smart Cache, RAG на PostgreSQL)
**Цель:** сделать приложение безопасным для доступа по локальной сети и поставить
его обычному пользователю как десктопное приложение без обязательного Docker.

**Документы-источники:** [`docs/SPEC.md`](docs/SPEC.md),
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md),
[`docs/RULES.md`](docs/RULES.md).

---

## 1. Принципы v1.0.0

- **Read-only по умолчанию** сохраняется: аутентификация не даёт новых прав на
  мутации, только закрывает доступ к API.
- **Fail-closed:** при `AUTH_ENABLED=true` любой неаутентифицированный запрос к
  защищённому API получает `401`, а не «тихий» доступ.
- **Секреты не логируются и не возвращаются API:** пароли, JWT, cookie,
  `client_secret`, `access_token`.
- **Один пользователь:** v1.0.0 — single-user auth, без регистрации, ролей и
  мультитенантности. Это осознанно, см. §2 SPEC.
- **Desktop — не второй продукт:** тот же React UI и FastAPI backend, упакованные
  в Tauri; Docker остаётся серверным вариантом.
- **ADR first:** auth и desktop-упаковка фиксируются в ADR-0016/ADR-0017 до кода.

### Вне области v1.0.0

- Мультипользовательский режим, RBAC, команды и приглашения.
- OAuth/SSO (GitHub, Google, корпоративный LDAP).
- Мобильные приложения.
- Встроенный PostgreSQL/pgvector в desktop-сборке (кандидат v1.1).
- Облачная синхронизация Saved Views и истории статусов.

---

## 2. Спринт 47 — Single-User Authentication

**Цель:** защитить приложение при доступе по LAN, не усложняя локальный
single-user сценарий.

### 2.1. Контракты

- Таблица `users`: `id`, `username` (unique), `hashed_password` (bcrypt),
  `is_active`, `created_at`, `last_login_at`.
- Bootstrap при пустой таблице: `ADMIN_USERNAME` + `ADMIN_PASSWORD` из `.env`.
  Пароль в открытом виде не хранится; при `AUTH_ENABLED=true` пользователь
  создаётся, пароль сразу хэшируется bcrypt.
- JWT: HS256, `sub` = user id, `iat`, `exp`, `jti`; секрет
  `AUTH_JWT_SECRET` (≥32 байта), TTL `AUTH_TOKEN_TTL_SECONDS` (default 604800 —
  7 дней).
- Эндпоинты:
  - `POST /api/v1/auth/login` → `{access_token, token_type, expires_at, user}` и
    `Set-Cookie: iiruchating_session=...; HttpOnly; SameSite=Lax; Path=/`
    (`Secure` — при HTTPS);
  - `GET /api/v1/auth/me` → текущий пользователь;
  - `POST /api/v1/auth/logout` → очищает cookie, `204`.
- Middleware принимает cookie **или** `Authorization: Bearer <token>`.
- Исключения без токена: `/api/v1/health`, `/api/v1/metrics`,
  `/api/v1/auth/login`; остальное — `401`.
- Ошибки: `401 invalid_credentials`, `429 too_many_attempts`,
  `401 token_expired`, `403 user_disabled`.
- Rate-limit логина: не более 5 попыток / 60 с на IP+username.
- `AUTH_ENABLED`: default `true`; для локального `127.0.0.1` можно выключить
  (`false`). В Docker/LAN рекомендуется `true`. Явное значение всегда
  приоритетнее.

### 2.2. Задачи

- [x] **S47-001. ADR-0016 «Single-user authentication»:** threat model, cookie vs
      Bearer, JWT secret rotation, rate-limit, fail-closed.
- [x] **S47-002. Миграция `012_users`:** таблица `users`, индексы, bootstrap из
      `.env`; `AuthService` с bcrypt (cost ≥ 12).
- [x] **S47-003. API:** `login`/`me`/`logout`, JWT issue/verify, rate-limit,
      аудит неуспешных попыток без логирования пароля.
- [x] **S47-004. Защита API:** middleware/dependency для всех роутов, кроме
      health/metrics/login; тесты на обход.
- [x] **S47-005. Frontend:** `AuthProvider`, `/login`, protected routes,
      редирект на `/login`, logout, обработка `401`, RU/EN, `aria`.
- [x] **S47-006. Тесты и E2E:** bcrypt, JWT expiry, cookie/Bearer, exemptions,
      rate-limit, отсутствие hash/секретов в ответах, login E2E.

### 2.3. Definition of Done

- [x] При `AUTH_ENABLED=true` все защищённые API отвечают `401` без валидного
      токена/cookie; `/health` и `/metrics` доступны.
- [x] Логин выдаёт JWT и httpOnly cookie; logout очищает сессию.
- [x] Пароли хранятся только как bcrypt-hash; в логах/ответах нет пароля, hash,
      JWT и cookie.
- [x] Frontend не показывает данные до `/auth/me`; после истечения токена —
      редирект на `/login`.
- [x] `pytest`, `ruff`, `mypy`, `pnpm typecheck/lint/test/build`, E2E — зелёные.
- [x] ADR-0016, SPEC §3.28, README и `.env.example` обновлены.

---

## 3. Спринт 48 — Tauri Desktop App

**Цель:** собрать Windows/macOS приложение, которое запускает backend
автоматически и не требует Docker для обычного пользователя.

### 3.1. Архитектура

```
Tauri shell (Rust)
  ├─ spawn sidecar: iiruchating-backend(.exe) --port <free> --data-dir <appdata>
  ├─ health poll: GET /api/v1/health до db_ok=true
  ├─ webview: React UI → http://127.0.0.1:<port>
  └─ on exit: graceful shutdown sidecar (SIGTERM/CTRL_BREAK), fallback kill
```

- Backend собирается PyInstaller (one-folder) в `sidecar/`; в Tauri —
  `bundle.externalBin`.
- Данные: `%APPDATA%/IIRuchating` (Windows) и
  `~/Library/Application Support/IIRuchating` (macOS); SQLite по умолчанию.
- Порт выбирается свободный, передаётся sidecar и webview; конфликт портов
  обрабатывается повтором.
- RAG в desktop: только при явно заданном внешнем PostgreSQL + pgvector;
  встроенный PostgreSQL — вне v1.0.0 (KI-019).
- Docker остаётся документированным серверным вариантом.

### 3.2. Задачи

- [x] **S48-001. ADR-0017 «Tauri desktop packaging»:** sidecar lifecycle,
  data dir, port allocation, code signing, update strategy.
- [x] **S48-002. PyInstaller sidecar:** сборка backend с pygit2/libgit2,
  аргументы `--port`/`--data-dir`, логи в app data, health endpoint.
- [x] **S48-003. Tauri shell:** spawn/stop sidecar, health poll, dynamic port,
  graceful shutdown, crash recovery, single-instance lock.
- [x] **S48-004. Frontend integration:** base URL из Tauri, auth token handoff,
  CSP, запрет remote-origin, offline/loading states.
- [x] **S48-005. Installers:** Windows `.msi`/NSIS `.exe`; macOS `.dmg` —
  отдельная CI-сборка в S49; иконки/версия/checksums.
- [x] **S48-006. Smoke/E2E:** запуск без Docker, health, dashboard, login,
  корректное завершение без orphan-процессов (Windows).

### 3.3. Definition of Done

- [x] Windows-сборка запускается на чистой машине без Python/Docker/Node
      (проверено на текущей Windows-машине).
- [x] Backend стартует автоматически, UI открывается после `db_ok=true`.
- [x] Закрытие приложения останавливает sidecar; повторный запуск не оставляет
      занятых портов/процессов.
- [x] Auth в desktop работает; токен не хранится в открытом `localStorage`
      (Bearer в памяти; повторный вход после перезапуска — KI-020).
- [x] Docker-режим не сломан; `docker compose up -d` по-прежнему работает.
- [x] Документация: установка, данные, логи, удаление, ограничения RAG.
- [x] ADR-0017, ARCHITECTURE §25, README, KI-019/KI-020 обновлены.

---

## 4. Спринт 49 — Release v1.0.0

**Цель:** финальный аудит, релизные артефакты и публикация v1.0.0.

### 4.1. Задачи

- [x] **S49-001. Security audit:** auth/JWT/cookie/CSRF/CORS/rate-limit,
      path traversal, secret scanning, dependency audit, Tauri CSP и sidecar.
- [x] **S49-002. Docs:** CHANGELOG `[1.0.0]`, RELEASES, README, SPEC,
      ARCHITECTURE, миграция v0.9.0 → v1.0.0, known issues.
- [x] **S49-003. Release build:** Windows `.msi`/NSIS `.exe`, checksums,
      GitHub Release, зеркало GitFlic; macOS — отдельная CI-сборка/notarization.
- [x] **S49-004. Final regression:** backend/frontend/E2E, bundle budget,
      smoke desktop, проверка SHA на обоих remote.

### 4.2. Definition of Done

- [x] Нет открытых critical/high уязвимостей; секреты не попадают в артефакты.
- [x] `pytest`, `ruff`, `mypy`, `pnpm typecheck/lint/test/build`,
      `pnpm test:e2e`, bundle budget — зелёные.
- [x] Windows-артефакты собраны и проверены; macOS — CI-сборка/notarization
      (на Windows не собирается).
- [x] Desktop-сборка использует backend SHA `0fdcf65…`; Docker-образ не
      публиковался в этом спринте.
- [x] Тег `v1.0.0`, GitHub Release, GitFlic mirror, README/CHANGELOG/RELEASES
      согласованы.
- [x] Известные ограничения (KI-019, KI-020, KI-021, KI-022) задокументированы.

---

## 5. Сквозной Definition of Done v1.0.0

- [ ] Все задачи спринтов 47–49 закрыты или перенесены в `KNOWN_ISSUES` с KI.
- [ ] `ruff check backend/app backend/tests` — 0.
- [ ] `mypy backend/app` — 0.
- [ ] `pytest -q` — passed; новые сервисы покрыты тестами.
- [ ] Frontend: typecheck, lint, unit, build, E2E — 0.
- [ ] Entry bundle < 90 kB gzip (lazy-страницы и словари).
- [ ] Read-only политика не нарушена; destructive-команды только через actions
      с подтверждением.
- [ ] Нет секретов, `.env`, ключей и токенов в диффе/артефактах.
- [ ] ADR-0016/0017, SPEC, ARCHITECTURE, README, CHANGELOG, RELEASES
      синхронизированы.

---

## 6. Открытые вопросы (решить в S47-001/S48-001)

1. **Auth default:** `AUTH_ENABLED=false` локально и `true` в Docker/LAN —
   подтвердить в ADR-0016.
2. **Cookie vs Bearer в Tauri:** web — httpOnly cookie; desktop — безопасное
   хранилище ОС (keychain) + Bearer fallback. Детали — ADR-0016/0017, KI-020.
3. **Desktop DB:** SQLite по умолчанию; RAG — только внешний PostgreSQL.
   Встроенный PostgreSQL/pgvector — v1.1 (KI-019).
4. **Code signing:** Windows Authenticode и macOS notarization требуют
   сертификатов; при их отсутствии — явное предупреждение в релизе.
5. **Password reset:** self-service отсутствует; сброс — через bootstrap/env и
   перезапуск. Мультипользовательский reset — вне v1.0.0.
