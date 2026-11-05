# IIRuchating — frontend

React 19 + TypeScript + Vite + Tailwind CSS.

## Запуск

```bash
# из корня репозитория
pnpm --dir frontend install
pnpm --dir frontend dev
```

Dev-сервер: <http://127.0.0.1:5173>. Запросы `/api` проксируются на
`http://127.0.0.1:8000` (backend должен быть запущен).

## Проверки

```bash
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend test
pnpm --dir frontend build
```
