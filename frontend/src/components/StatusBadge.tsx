interface StatusBadgeProps {
  state: string | null | undefined
  tracked: boolean
  stale?: boolean
}

const LABELS: Record<string, string> = {
  current: 'current',
  ahead: 'ahead',
  behind: 'behind',
  diverged: 'diverged',
  dirty: 'dirty',
  no_upstream: 'no upstream',
  detached: 'detached',
  error: 'error',
  unknown: 'нет статуса',
}

const ICONS: Record<string, string> = {
  current: '✓',
  ahead: '↑',
  behind: '↓',
  diverged: '⚠',
  dirty: '!',
  no_upstream: '?',
  detached: '⚓',
  error: '✕',
  unknown: '·',
}

const STYLES: Record<string, string> = {
  current: 'bg-emerald-100 text-emerald-800 ring-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-300 dark:ring-emerald-800',
  ahead: 'bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:ring-amber-800',
  behind: 'bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:ring-amber-800',
  dirty: 'bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:ring-amber-800',
  diverged: 'bg-red-100 text-red-800 ring-red-200 dark:bg-red-900/40 dark:text-red-300 dark:ring-red-800',
  error: 'bg-red-100 text-red-800 ring-red-200 dark:bg-red-900/40 dark:text-red-300 dark:ring-red-800',
  no_upstream: 'bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-600',
  detached: 'bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-600',
  unknown: 'bg-slate-100 text-slate-500 ring-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:ring-slate-600',
}

export default function StatusBadge({ state, tracked, stale = false }: StatusBadgeProps) {
  if (!tracked) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-600">
        <span aria-hidden="true">○</span> untracked
      </span>
    )
  }

  const key = state ?? 'unknown'
  const style = STYLES[key] ?? STYLES.unknown
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style} ${
        stale ? 'opacity-60' : ''
      }`}
      aria-label={LABELS[key] ?? key}
    >
      <span aria-hidden="true">{ICONS[key] ?? '·'}</span>
      {LABELS[key] ?? key}
      {stale && (
        <span title="Данные устарели — обновите статус" aria-label="устарело">
          🕒
        </span>
      )}
    </span>
  )
}
