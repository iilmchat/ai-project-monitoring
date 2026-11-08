# ADR-0012: Мультипровайдерные AI-профили и GigaChat OAuth

**Статус:** Accepted
**Дата:** 2026-11-08
**Контекст:** Спринт 43 (S43-001..S43-004), v0.9.0 «Search & Reliability»

## Контекст

В v0.8.0 существовал только OpenAI-совместимый тип AI-провайдера: `base_url`,
`api_key`, `model_name`. Этого достаточно для LM Studio, Ollama, DeepSeek и
OpenRouter, но GigaChat требует OAuth 2.0: `client_id`, `client_secret`,
`scope` и периодическое обновление access token (≈30 минут).

Нужно добавить второй тип провайдера, не ломая существующие профили и не
возвращая секреты в API/логи.

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| Отдельная таблица `gigachat_profiles` | Чистое разделение | Дублирование CRUD/активации, два источника активного профиля |
| Один тип + `api_key` как access token | Минимум изменений | Нет refresh, токен быстро истекает, пользователь вручную обновляет |
| Поля OAuth в `ai_provider_profiles` + адаптер | Единый CRUD и `is_active`, обратная совместимость | Больше nullable-колонок |

## Решение

- В `ai_provider_profiles` добавлены `provider_type`
  (`openai_compatible` | `gigachat`), `auth_type` (`api_key` | `oauth`),
  `client_id`, `client_secret`, `oauth_scope`, `oauth_expires_at`,
  `access_token` (server-only). Миграция `010`; существующие строки получают
  `openai_compatible`/`api_key`.
- `GigaChatProvider` инкапсулирует OAuth, in-memory кэш токена по `profile_id`,
  single-flight refresh и повтор запроса после `401`.
- `LLMService.resolve()` выбирает адаптер по `provider_type`; OpenAI-совместимые
  профили работают без изменений.
- API `POST /settings/ai-providers/gigachat/auth` создаёт/обновляет профиль по
  `profile_name` и **никогда** не возвращает `client_secret`/`access_token`.
- `POST /settings/ai-providers/{id}/gigachat/refresh` обновляет токен без
  повторного ввода секрета.

## Последствия

- Один активный профиль любого типа; переключение — существующим `activate`.
- Секреты хранятся в БД и не попадают в ответы, `action_log`, `ai_cache` и
  structlog.
- GigaChat — облачный провайдер, поэтому проверка `LLM_ALLOW_REMOTE` для него не
  применяется; OpenAI-совместимые remote-endpoint'ы по-прежнему требуют
  `LLM_ALLOW_REMOTE=true`.
- При смене OAuth-эндпоинта/scope потребуется миграция или повторная
  авторизация; токен живёт ~30 минут (KI-018).
