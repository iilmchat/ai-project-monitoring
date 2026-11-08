# ADR-0017: Tauri desktop packaging

**Статус:** Accepted
**Дата:** 2026-11-08
**Контекст:** Спринт 48 (S48-001..S48-004), v1.0.0 «Secure Desktop»

## Контекст

Пользователю нужен Windows/macOS клиент без Python, Node и Docker. React-UI и
FastAPI-backend уже существуют; нужно упаковать их в одно приложение, обеспечить
запуск/остановку backend и работу с локальной SQLite.

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| Tauri + Python sidecar | Малый shell, нативный WebView2/WKWebView, Rust-контроль процессов | Нужна сборка PyInstaller и Rust-тулчейн |
| Electron + Python | Зрелая экосистема | Большой bundle, Node runtime, тяжёлый shell |
| Только Docker | Единый серверный сценарий | Не подходит обычному пользователю |
| Полный Python GUI | Один язык | Нет текущего React UI |

## Решение

- Tauri 2 shell (`frontend/src-tauri`) запускает React из `frontend/dist`.
- Backend собирается PyInstaller `--onefile --noconsole` в
  `backend/build_sidecar.py`; итоговый бинарник копируется в
  `frontend/src-tauri/binaries/iiruchating-backend-<target-triple>.exe`.
- Sidecar запускается на свободном `127.0.0.1:<port>`; Tauri передаёт
  `--port` и `--data-dir` (`%APPDATA%/IIRuchating`, macOS Application Support).
- `TAURI_MODE=true` в `config.py` принудительно переключает backend на SQLite в
  app-data; RAG остаётся доступен только с внешним PostgreSQL (KI-019).
- Sidecar использует process group/job object и `kill_on_drop`; при
  `RunEvent::Exit` Tauri убивает всё дерево процессов, включая дочерний процесс
  PyInstaller onefile.
- Frontend `main.tsx` показывает splash и ждёт `GET /api/v1/health`
  (`status=ok`) перед монтированием React.
- В Tauri API base URL передаётся через `backend_url`; auth использует Bearer
  fallback (KI-020).
- CSP разрешает только `self` и `http://127.0.0.1:*`; внешние origin запрещены.
- Docker Compose остаётся серверным вариантом; desktop-сборка и Docker
  используют один backend SHA.

## Последствия

- Windows-сборка проверена: `.msi` и NSIS `.exe`; macOS требует отдельной
  CI-сборки и notarization (S49).
- PyInstaller onefile распаковывается во временный каталог; libgit2/pygit2
  включены через `--collect-all`.
- Desktop по умолчанию без RAG (SQLite); для RAG нужен внешний PostgreSQL.
- Обновление приложения — через Tauri updater (план S49); данные в app-data
  сохраняются.
