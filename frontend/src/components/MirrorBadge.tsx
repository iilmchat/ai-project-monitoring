interface MirrorBadgeProps {
  status: string | null | undefined
}

const LABELS: Record<string, string> = {
  in_sync: 'in sync',
  not_applicable: 'n/a',
  unavailable: 'unavailable',
  missing_on_gitflic: 'missing on GitFlic',
  missing_on_github: 'missing on GitHub',
  behind_gitflic: 'behind GitFlic',
  behind_github: 'behind GitHub',
  diverged: 'diverged',
  history_rewritten: 'history rewritten',
}

const STYLES: Record<string, string> = {
  in_sync: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  not_applicable: 'bg-slate-100 text-slate-500 ring-slate-200',
  unavailable: 'bg-slate-100 text-slate-600 ring-slate-200',
  missing_on_gitflic: 'bg-amber-100 text-amber-800 ring-amber-200',
  missing_on_github: 'bg-amber-100 text-amber-800 ring-amber-200',
  behind_gitflic: 'bg-amber-100 text-amber-800 ring-amber-200',
  behind_github: 'bg-amber-100 text-amber-800 ring-amber-200',
  diverged: 'bg-red-100 text-red-800 ring-red-200',
  history_rewritten: 'bg-red-100 text-red-800 ring-red-200',
}

export default function MirrorBadge({ status }: MirrorBadgeProps) {
  if (!status) {
    return <span className="text-xs text-slate-400">—</span>
  }
  const style = STYLES[status] ?? STYLES.unavailable
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}
    >
      {LABELS[status] ?? status}
    </span>
  )
}
