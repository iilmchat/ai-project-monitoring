import { Link, Outlet } from 'react-router-dom'

export default function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-900 text-sm font-bold text-white">
              II
            </span>
            <span className="text-lg font-semibold tracking-tight">IIRuchating</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm font-medium text-slate-600">
            <Link to="/" className="hover:text-slate-900">
              Дашборд
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        IIRuchating · мониторинг локальных Git-репозиториев (read-only)
      </footer>
    </div>
  )
}
