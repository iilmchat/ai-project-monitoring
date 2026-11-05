import { Link, Outlet } from 'react-router-dom'

import ThemeToggle from './ThemeToggle'

export default function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-outline-variant bg-white dark:bg-slate-900 shadow-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-3">
            <img
              src="/logo-icon.svg"
              alt="ai-project-monitoring"
              width={36}
              height={36}
              className="h-9 w-9 dark:invert"
            />
            <span className="flex flex-col leading-tight">
              <span className="logo-text text-lg tracking-tight">ai-project-monitoring</span>
              <span className="text-xs font-normal text-on-surface-variant">
                мониторинг и анализ локальных проектов
              </span>
            </span>
          </Link>
          <nav className="flex items-center gap-4 text-sm font-medium text-on-surface-variant">
            <Link to="/" className="hover:text-primary">
              Дашборд
            </Link>
            <ThemeToggle />
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-outline-variant bg-white dark:bg-slate-900 py-4 text-center text-xs text-on-surface-variant">
        ai-project-monitoring · мониторинг локальных Git-репозиториев (read-only)
      </footer>
    </div>
  )
}
