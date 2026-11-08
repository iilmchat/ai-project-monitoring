# ADR-0016: Single-user authentication

**Статус:** Accepted
**Дата:** 2026-11-08
**Контекст:** Спринт 47 (S47-001..S47-004), v1.0.0 «Secure Desktop»

## Контекст

Приложение однопользовательское и по умолчанию работает локально. При доступе
по LAN API без аутентификации позволяет любому в сети читать состояние
репозиториев, настройки и запускать подтверждённые действия. Нужна простая
защита без регистрации, ролей и мультитенантности.

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| Только bind на `127.0.0.1` | Нет кода | Не работает для LAN/удалённого доступа |
| HTTP Basic Auth | Просто | Пароль передаётся в каждом запросе; плохой UX |
| Single-user + JWT + httpOnly cookie | Один пользователь, stateless, безопасное хранение в браузере | Нужны bcrypt/PyJWT и обработка expiry |
| OAuth/SSO | Гибко | Избыточно для одного пользователя |

## Решение

- Таблица `users` (`id`, `username* UNIQUE`, `hashed_password`, `is_active`,
  `created_at`, `last_login_at`), миграция `012`.
- Пароли — bcrypt (cost ≥ 12). Bootstrap при пустой таблице:
  `ADMIN_USERNAME`/`ADMIN_PASSWORD` (default `admin`/`admin`), пароль сразу
  хэшируется.
- JWT HS256 (`sub`, `iat`, `exp`, `jti`), TTL `AUTH_TOKEN_TTL_SECONDS`
  (default 604800 — 7 дней), секрет `AUTH_JWT_SECRET` (≥32 байта; пустой —
  эфемерный секрет с предупреждением).
- `POST /auth/login` выдаёт JWT и ставит `iiruchating_session` cookie:
  `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` при HTTPS.
- `AuthMiddleware` принимает cookie или `Authorization: Bearer`, защищает все
  `/api/v1/*`, кроме `/health`, `/metrics`, `/auth/login`.
- `GET /auth/me`, `POST /auth/logout`; login rate-limit 5/60 с на IP+username.
- `AUTH_ENABLED` позволяет выключить auth для локального режима; по умолчанию
  включён.

## Последствия

- Появляются зависимости `bcrypt` и `PyJWT` (зафиксированы в requirements).
- JWT нельзя отозвать до истечения; logout очищает cookie, но украденный токен
  жив до `exp`. При необходимости — короткий TTL/rotation в v1.1.
- Секрет JWT должен быть стабильным между перезапусками; пустой секрет делает
  токены недействительными после рестарта.
- Desktop-приложение использует Bearer fallback и OS keychain (KI-020).
- Read-only политика не меняется: auth только закрывает доступ.
