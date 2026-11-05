import { useEffect } from 'react'

interface KeyboardShortcutsModalProps {
  open: boolean
  onClose: () => void
}

const SHORTCUTS: { keys: string; description: string }[] = [
  { keys: 'Ctrl / Cmd + K', description: 'Открыть Command Palette' },
  { keys: '?', description: 'Показать горячие клавиши' },
  { keys: '/', description: 'Фокус в поле поиска' },
  { keys: '↑ / ↓', description: 'Навигация по таблице' },
  { keys: 'Enter', description: 'Открыть репозиторий / выполнить' },
  { keys: 'Space', description: 'Выбрать строку (batch selection)' },
  { keys: 'Esc', description: 'Закрыть модалку / снять фокус' },
]

export default function KeyboardShortcutsModal({
  open,
  onClose,
}: KeyboardShortcutsModalProps) {
  useEffect(() => {
    if (!open) {
      return
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) {
    return null
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Горячие клавиши"
        className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Горячие клавиши
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Работают, когда фокус не находится в поле ввода.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            ×
          </button>
        </div>
        <dl className="mt-4 grid gap-2 sm:grid-cols-2">
          {SHORTCUTS.map((shortcut) => (
            <div
              key={shortcut.keys}
              className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700"
            >
              <dt>
                <kbd className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                  {shortcut.keys}
                </kbd>
              </dt>
              <dd className="text-right text-xs text-slate-600 dark:text-slate-400">
                {shortcut.description}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}
