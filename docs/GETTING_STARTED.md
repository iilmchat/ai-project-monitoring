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
GITHUB_TOKEN=<your-github-pat>          # опционально (зарезервировано для v0.2.0)
STATUS_TTL_SECONDS=60
COMPARE_TTL_SECONDS=60
FETCH_TIMEOUT=30
DATABASE_URL=sqlite+aiosqlite:///./data/iiruchating.db
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

SQLite-файл сохраняется в `./data/` (volume). Backend при старте выполняет
`alembic upgrade head`. Nginx проксирует `/api` на сервис `backend`.

Каталог с проектами монтируется в контейнер: по умолчанию
`C:/Projects:/projects`, а `SCAN_ROOTS=/projects`. Если ваши репозитории
лежат в другом месте, измените путь в `docker-compose.yml` (`volumes`) и
`SCAN_ROOTS` — иначе сканирование найдёт 0 репозиториев.

Остановить: `docker compose down`.

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