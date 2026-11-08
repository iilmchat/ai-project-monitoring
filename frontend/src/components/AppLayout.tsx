import { Suspense, lazy, useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'

import { useI18n } from '../i18n'
import LanguageToggle from './LanguageToggle'
import ThemeToggle from './ThemeToggle'

const CommandPalette = lazy(() => import('./CommandPalette'))
const KeyboardShortcutsModal = lazy(() => import('./KeyboardShortcutsModal'))

export default function AppLayout() {
  const { t } = useI18n()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const typing =
        target !== null &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable)
      if (typing) {
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen(true)
      } else if (event.key === '?') {
        event.preventDefault()
        setShortcutsOpen(true)
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-outline-variant bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-3">
            <img
              src="/logo-icon.svg"
              alt={t('app.title')}
              width={36}
              height={36}
              className="h-9 w-9 dark:invert"
            />
            <span className="flex flex-col leading-tight">
              <span className="logo-text text-lg tracking-tight dark:text-slate-100">
                {t('app.title')}
              </span>
              <span className="text-xs font-normal text-on-surface-variant dark:text-slate-400">
                {t('app.subtitle')}
              </span>
            </span>
          </Link>
          <nav className="flex items-center gap-4 text-sm font-medium text-on-surface-variant dark:text-slate-300">
            <Link to="/" className="hover:text-primary">
              {t('nav.dashboard')}
            </Link>
            <Link
              to="/settings"
              className="inline-flex items-center gap-1 hover:text-primary"
              title={t('nav.settings')}
            >
              <span aria-hidden="true">⚙</span> {t('nav.settings')}
            </Link>
            <LanguageToggle />
            <ThemeToggle />
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-outline-variant bg-white py-4 text-center text-xs text-on-surface-variant dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
        <p>{t('footer.text')}</p>
        <p className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">
          {t('footer.hint')}
        </p>
      </footer>

      {paletteOpen && (
        <Suspense fallback={null}>
          <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
        </Suspense>
      )}
      {shortcutsOpen && (
        <Suspense fallback={null}>
          <KeyboardShortcutsModal
            open={shortcutsOpen}
            onClose={() => setShortcutsOpen(false)}
          />
        </Suspense>
      )}
    </div>
  )
}
