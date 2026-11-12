# GETTING_STARTED — развёртывание за ~10 минут

## 1. Требования

| Инструмент | Версия |
|------------|--------|
| Python | 3.12 (локально допустим 3.11 — KI-004) |
| Node.js | 20+ (для Vite 8 — 20.19+) |
| pnpm | 10+ |
| Docker Desktop | актуальный |
| Git | 2.40+ (для fetch/rev-list) |

---

## 2. Клонирование и настройка

```bash
git clone https://github.com/iilmchat/ai-project-monitoring.git
cd iiruchating
cp .env.example .env
```

Заполните в `.env`:

```env
# В Docker путь внутри контейнера (host-каталог монтируется в /projects)
SCAN_ROOTS=/projects
SCAN_DEPTH=3
SCAN_IGNORE=node_modules,.venv,vendor,dist,build,target
GITHUB_TOKEN=<your-github-pat>          # опционально
STATUS_TTL_SECONDS=60
COMPARE_TTL_SECONDS=60
FETCH_TIMEOUT=30

# PostgreSQL (используется docker-compose db service и RAG)
POSTGRES_USER=iiruchating
POSTGRES_PASSWORD=password
POSTGRES_DB=iiruchating
# Docker Compose задаёт DATABASE_URL сам. Для локального запуска с PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://iiruchating:password@127.0.0.1:5432/iiruchating

# Эмбеддинги для RAG (OpenAI-compatible /v1/embeddings)
EMBEDDING_BASE_URL=http://127.0.0.1:1234/v1
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
EMBEDDING_ALLOW_REMOTE=false
```

Для локального запуска без Docker укажите реальные хостовые пути
(например, `SCAN_ROOTS=C:/Projects`).

---

## 3. Запуск (Docker)

```bash
docker compose up -d --build
```

- Frontend (UI): <http://127.0.0.1:3000>
- API: <http://127.0.0.1:8000/api/v1/health>

Compose поднимает три сервиса:

| Сервис | Назначение |
|---|---|
| `db` | PostgreSQL 16 + `pgvector` (`pgvector/pgvector:pg16`), volume `./pgdata` |
| `backend` | FastAPI + Alembic; ждёт healthy `db`, выполняет `alembic upgrade head` |
| `frontend` | Nginx + собранный React UI |

Backend при старте выполняет `alembic upgrade head` через
`backend/docker-entrypoint.sh` (миграция `011` создаёт `code_chunks` и HNSW-индекс
на PostgreSQL). Nginx проксирует `/api` на сервис `backend`.

PostgreSQL-данные сохраняются в `./pgdata/` (добавлен в `.gitignore`). SQLite
поддерживается для локального запуска без Docker: RAG на нём работает через
`sqlite-vec`, а при недоступном расширении — через Python-fallback.

Каталог с проектами монтируется в контейнер: по умолчанию
`${PROJECTS_ROOT:-C:/Projects}:/projects`, а `SCAN_ROOTS=/projects`. Если ваши
репозитории лежат в другом месте, задайте `PROJECTS_ROOT` и
`DOCKER_PATH_MAP=<host-root>=/projects` (или измените `volumes`/`SCAN_ROOTS`) —
иначе сканирование найдёт 0 репозиториев.

Остановить: `docker compose down`.

### Docker-статус контейнеров (v0.5.0)

Backend монтирует Docker-сокет хоста read-only и показывает статус контейнеров
проекта в деталях репозитория:

- В `docker-compose.yml`: `/var/run/docker.sock:/var/run/docker.sock:ro`,
  `DOCKER_HOST=unix:///var/run/docker.sock`.
- `DOCKER_PATH_MAP` переводит host-пути compose-проектов в пути backend-контейнера.
  Для стандартного mount `C:/Projects:/projects` значение по умолчанию —
  `C:/Projects=/projects`. Если проекты лежат в другом месте, задайте
  `PROJECTS_ROOT` (источник volume) и пару
  `DOCKER_PATH_MAP=<host-root>=/projects`.
- На Windows при локальном запуске (без Docker) оставьте `DOCKER_HOST` пустым:
  Docker SDK выберет named pipe `\\.\pipe\docker_engine`.
- Проверка: `curl http://127.0.0.1:8000/api/v1/repositories/1/docker`.
- Если Docker Desktop не запущен или доступ к сокету запрещён, API вернёт
  `status: "unavailable"` и текст ошибки; остальной дашборд продолжит работать.
  Подробности — KI-009.

### Проверка зависимостей (v0.5.0, Sprint 25)

Backend читает `requirements.txt` в корне репозитория и сверяет версии с PyPI:

- `GET /api/v1/repositories/{id}/dependencies?ecosystem=python`.
- `refresh=true` запускает повторную проверку, иначе используется кэш
  `dependency_cache` с TTL 24 часа.
- `pip`/`npm` не запускаются; читаются только манифесты внутри репозитория.
- Node: `ecosystem=node` читает `package.json` и проверяет версии через npm
  registry; `ecosystem=all` объединяет Python и Node.

---

## 3.1. Использование PostgreSQL и RAG

PostgreSQL включается автоматически в Docker Compose. Для локального backend:

```bash
docker compose up -d db
# в .env:
# DATABASE_URL=postgresql+asyncpg://iiruchating:password@127.0.0.1:5432/iiruchating
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Проверка подключения:

```bash
curl http://127.0.0.1:8000/api/v1/health
# {"status":"ok","version":"1.0.0","db_ok":true,...}
```

### Вход в приложение

При `AUTH_ENABLED=true` (по умолчанию) при первом запуске создаётся пользователь
`admin` с паролем `admin`. Смените его в `.env`:

```env
AUTH_ENABLED=true
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>
AUTH_JWT_SECRET=<random-64-char-string>
```

Для локального одноразового запуска можно отключить вход: `AUTH_ENABLED=false`.
Health и metrics остаются публичными; остальные API требуют JWT (cookie
`iiruchating_session` или `Authorization: Bearer`).

Миграции применяются автоматически при старте контейнера
(`docker-entrypoint.sh` → `alembic upgrade head`). Вручную:

```bash
docker compose exec backend alembic upgrade head
```

### Индексация и поиск

1. Настройте эмбеддинги в `.env` (OpenAI-compatible `/v1/embeddings`):

```env
EMBEDDING_BASE_URL=http://127.0.0.1:1234/v1
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
EMBEDDING_ALLOW_REMOTE=false
```

Для локальной LM Studio используйте её base URL и модель эмбеддингов,
например `nomic-embed-text-v1.5` (тогда задайте `EMBEDDING_DIMENSIONS=768` и
пересоздайте таблицу `code_chunks` миграцией/переиндексацией).

Начиная с v1.4.2 модель эмбеддингов задаётся в
**Настройки → AI Провайдеры** (поле «Модель для эмбеддингов (RAG)»); она имеет
приоритет над `EMBEDDING_MODEL`. Если активный профиль существует, но поле
пустое, поиск вернёт `embedding_model_not_configured` — чат-модель для RAG не
подставляется.

Начиная с v1.4.4 размерность, размер чанка и перекрытие меняются в
**Настройки → «Настройки RAG (Поиск по коду)»** без редактирования `.env`.
Для `nomic-embed-text` укажите `EMBEDDING_DIMENSIONS=768`, затем
переиндексируйте код. Перед индексацией выполняется пробный `embed("test")`;
если фактическая длина вектора не совпадает с настройкой, возвращается
`dimension_mismatch` с фактическим и ожидаемым значением.

2. Запустите индексацию из UI (`/search` → «Запустить индексацию (RAG)») или
через API:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/search/code/index \
  -H "Content-Type: application/json" -d "{}"

curl http://127.0.0.1:8000/api/v1/search/code/status
```

3. Поиск:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/search/code \
  -H "Content-Type: application/json" \
  -d '{"query":"где у меня настроен Redis?","limit":5}'
```

RAG работает на PostgreSQL + `pgvector` и на SQLite + `sqlite-vec` (desktop).
Если `sqlite-vec` не загрузился, поиск автоматически считает косинус в Python;
без модели эмбеддингов эндпоинты отвечают `503 embedding_unavailable`, остальные
функции приложения продолжают работать.
Интеграционный тест: `TEST_DATABASE_URL=postgresql+asyncpg://... pytest -q
tests/test_rag_postgres.py`.

---

## 4. Локальный запуск (без Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

UI: <http://127.0.0.1:5173>. Vite проксирует `/api` на `127.0.0.1:8000`.

---

## 5. Проверки качества

```bash
# Backend
ruff check app tests
mypy app
pytest -q

# Frontend
pnpm typecheck && pnpm lint && pnpm test && pnpm build
```

---

## 6. Типичные проблемы

| Симптом | Причина | Решение |
|---------|---------|---------|
| «Репозиторий не найден» | `SCAN_ROOTS` неверный или глубина мала | Проверить путь, увеличить `SCAN_DEPTH` |
| `ahead/behind = 0`, хотя на remote есть коммиты | fetch не выполнялся | Проверить `GITHUB_TOKEN`, сеть; нажать «Обновить» |
| `remote_status = unavailable` | Нет доступа к remote | Проверить URL remote, токен, сеть |
| `Fetch timed out after 30s` в логах | Медленная сеть или очень большой репозиторий | Увеличить `FETCH_TIMEOUT` (например, 120) и повторить |
| `pygit2` не устанавливается | Нет libgit2 | Установить `libgit2` (Linux: `apt install libgit2-dev`) или использовать Docker |
| Docker: permission denied на `/repos` | Монтирование директории с репозиториями | Добавить volume с правильными правами |

---

## 7. Синхронизация с GitFlic (Зеркало)

Основной провайдер — GitHub (`origin`). Зеркало — GitFlic (`gitflic`). Автоматическое зеркалирование GitFlic не используется (см. KI-006 в `docs/KNOWN_ISSUES.md`), синхронизация выполняется вручную после пуша в GitHub:

```powershell
# 1. Пушим в GitHub
git push origin main

# 2. Зеркалируем в GitFlic
git push gitflic main

# 3. Проверяем, что SHA совпадают (опционально)
$ghSha = (git ls-remote origin main).Split()[0]
$gfSha = (git ls-remote gitflic main).Split()[0]
if ($ghSha -eq $gfSha) { Write-Host "OK: mirror in_sync" }
```

---

## 8. Настройка Webhook (опционально)

Webhook ускоряет реакцию на push (polling работает и без него). Для приёма
событий из интернета нужен публичный туннель:

```bash
# вариант 1: cloudflared
cloudflared tunnel --url http://localhost:8000

# вариант 2: ngrok
ngrok http 8000
```

Полученный URL указывается в настройках провайдера:

| Провайдер | Payload URL | Secret | События |
|-----------|-------------|--------|---------|
| GitHub | `https://<your-url>/api/v1/webhooks/github` | `WEBHOOK_SECRET` из `.env` | push, branch |
| GitFlic | `https://<your-url>/api/v1/webhooks/gitflic` | `WEBHOOK_SECRET` | push |

Если `WEBHOOK_SECRET` задан, запросы без корректной HMAC-подписи
(`X-Hub-Signature-256` для GitHub, `X-Gitflic-Signature` для GitFlic)
отклоняются с 401. Webhook инвалидирует кэш зеркала; polling остаётся
страховкой, если событие потерялось.

---

## 9. Настройка GitHub Actions для релизов

Релизы desktop-приложения собираются workflow
`.github/workflows/release-desktop.yml` при пуше тега `v*`. Сборка идёт на
`windows-latest`: Python-sidecar (PyInstaller) → `tauri-action` → GitHub Release
с `.msi`, NSIS `.exe`, подписями `.sig` и `latest.json` для автообновления.

### 9.1. Ключи подписи обновлений

Ключи создаются один раз (Rust не требуется, используется Tauri CLI):

```bash
cd frontend
pnpm tauri signer generate -w ~/.tauri/myapp.key
```

Будут созданы `myapp.key` (приватный) и `myapp.key.pub` (публичный). Публичный
ключ уже вставлен в `frontend/src-tauri/tauri.conf.json` → `plugins.updater.pubkey`.
Приватный ключ и пароль **не коммитятся** в git.

Добавьте в GitHub → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Значение |
|--------|----------|
| `TAURI_PRIVATE_KEY` | Полное содержимое файла `myapp.key` (включая строки `untrusted comment:` / `trusted comment:` и base64-блок) |
| `TAURI_KEY_PASSWORD` | Пароль, указанный при генерации ключа |

Workflow передаёт их в `tauri-action` как `TAURI_SIGNING_PRIVATE_KEY` и
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD` (имена Tauri v2), поэтому ничего больше
настраивать не нужно.

### 9.2. Выпуск новой версии

1. Поднимите версию в трёх местах (Tauri берёт версию из `tauri.conf.json`, но
   она должна совпадать с `package.json` и `Cargo.toml`):
   - `frontend/package.json` → `version`;
   - `frontend/src-tauri/tauri.conf.json` → `version`;
   - `frontend/src-tauri/Cargo.toml` → `[package].version`.
2. Закоммитьте изменения и запушьте в `main`.
3. Поставьте тег и запушьте его:

   ```bash
   git tag v1.1.0
   git push origin v1.1.0
   ```

4. GitHub Actions соберёт приложение, подпишет обновление и опубликует Release.
   Установленные клиенты увидят его через
   `https://github.com/iilmchat/ai-project-monitoring/releases/latest/download/latest.json`.

Проверить сборку без тега можно вручную: **Actions → Release Desktop → Run workflow**
(`workflow_dispatch`).

### 9.3. Кросс-платформенная матрица (S53)

Начиная с Sprint 53 workflow собирает релиз в матрице:

| ОС | Runner | Артефакты |
|----|--------|-----------|
| Windows | `windows-latest` | `.msi`, NSIS `.exe` |
| macOS | `macos-latest` | `.dmg` (Apple Silicon) |
| Linux | `ubuntu-latest` | `.AppImage` |

Для Linux CI устанавливает `libwebkit2gtk-4.1-dev`,
`libayatana-appindicator3-dev`, `librsvg2-dev`, `patchelf`, `libxdo-dev`,
`libgtk-3-dev`, `build-essential`, `libssl-dev`; для macOS — `pkg-config`.
Python-sidecar (`backend/build_sidecar.py`) собирается под target triple каждой
ОС (`.exe` только на Windows). Подпись обновлений — те же Secrets
`TAURI_PRIVATE_KEY`/`TAURI_KEY_PASSWORD` (или `TAURI_SIGNING_*`).
macOS-сборка без Apple Developer ID вызывает предупреждение Gatekeeper — см.
KI-024.
