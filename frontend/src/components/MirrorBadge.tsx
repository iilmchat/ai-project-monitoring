import { mirrorLabel, useI18n } from '../i18n'

interface MirrorBadgeProps {
  status: string | null | undefined
}

const STYLES: Record<string, string> = {
  in_sync:
    'bg-emerald-100 text-emerald-800 ring-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-300 dark:ring-emerald-800',
  not_applicable:
    'bg-slate-100 text-slate-500 ring-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:ring-slate-600',
  unavailable:
    'bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-600',
  missing_on_gitflic:
    'bg-red-100 text-red-800 ring-red-200 dark:bg-red-900/40 dark:text-red-300 dark:ring-red-800',
  missing_on_github:
    'bg-red-100 text-red-800 ring-red-200 dark:bg-red-900/40 dark:text-red-300 dark:ring-red-800',
  behind_gitflic:
    'bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:ring-amber-800',
  behind_github:
    'bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:ring-amber-800',
  diverged:
    'bg-red-100 text-red-800 ring-red-200 dark:bg-red-900/40 dark:text-red-300 dark:ring-red-800',
  history_rewritten:
    'bg-red-100 text-red-800 ring-red-200 dark:bg-red-900/40 dark:text-red-300 dark:ring-red-800',
}

export default function MirrorBadge({ status }: MirrorBadgeProps) {
  const { t } = useI18n()
  if (!status) {
    return <span className="text-xs text-slate-400 dark:text-slate-500">—</span>
  }
  const style = STYLES[status] ?? STYLES.unavailable
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}
      title={status}
    >
      {mirrorLabel(status, t)}
    </span>
  )
}
