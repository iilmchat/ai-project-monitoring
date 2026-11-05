interface StatusBadgeProps {
  state: string | null | undefined
  tracked: boolean
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

const STYLES: Record<string, string> = {
  current: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  ahead: 'bg-amber-100 text-amber-800 ring-amber-200',
  behind: 'bg-amber-100 text-amber-800 ring-amber-200',
  dirty: 'bg-amber-100 text-amber-800 ring-amber-200',
  diverged: 'bg-red-100 text-red-800 ring-red-200',
  error: 'bg-red-100 text-red-800 ring-red-200',
  no_upstream: 'bg-slate-100 text-slate-700 ring-slate-200',
  detached: 'bg-slate-100 text-slate-700 ring-slate-200',
  unknown: 'bg-slate-100 text-slate-500 ring-slate-200',
}

export default function StatusBadge({ state, tracked }: StatusBadgeProps) {
  if (!tracked) {
    return (
      <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-200">
        untracked
      </span>
    )
  }

  const key = state ?? 'unknown'
  const style = STYLES[key] ?? STYLES.unknown
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}
    >
      {LABELS[key] ?? key}
    </span>
  )
}
