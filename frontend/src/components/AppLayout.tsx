import { Link, Outlet } from 'react-router-dom'

export default function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-outline-variant bg-white shadow-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-3">
            <img
              src="/logo-icon.svg"
              alt="IIRuchating"
              width={36}
              height={36}
              className="h-9 w-9"
            />
            <span className="logo-text text-lg tracking-tight">IIRuchating</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm font-medium text-on-surface-variant">
            <Link to="/" className="hover:text-primary">
              Дашборд
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-outline-variant bg-white py-4 text-center text-xs text-on-surface-variant">
        IIRuchating · мониторинг локальных Git-репозиториев (read-only)
      </footer>
    </div>
  )
}
