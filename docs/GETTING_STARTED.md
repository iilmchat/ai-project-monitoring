# GETTING_STARTED — развёртывание за ~10 минут

## 1. Требования

| Инструмент | Версия |
|------------|--------|
| Python | 3.12 |
| Node.js | 20+ |
| pnpm | 10+ |
| Docker Desktop | актуальный |
| Git | 2.40+ (для fetch/compare) |

---

## 2. Клонирование и настройка

```bash
git clone https://github.com/iilmchat/iiruchating.git
cd iiruchating
cp .env.example .env
```

Заполните в `.env`:

```env
SCAN_ROOTS=/home/user/projects,/home/user/work
SCAN_DEPTH=3
SCAN_IGNORE=node_modules,.venv,vendor,dist,build,target
GITHUB_TOKEN=<your-github-pat>          # опционально, для Compare API GitHub
STATUS_TTL_SECONDS=60
DATABASE_URL=sqlite+aiosqlite:///./data/iiruchating.db
```

---

## 3. Запуск (Docker)

```bash
docker compose up -d --build
```

- Frontend: <http://127.0.0.1:8000>
- API: <http://127.0.0.1:8000/api/v1/health>

SQLite-файл сохраняется в `./data/` (volume).

---

## 4. Локальный запуск (без Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
pnpm install --allow-build=esbuild
pnpm dev
```

Vite проксирует `/api` на `127.0.0.1:8000`.

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