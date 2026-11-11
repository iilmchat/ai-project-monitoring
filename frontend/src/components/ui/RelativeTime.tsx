import { useId } from 'react'

import { useI18n } from '../../i18n'
import { formatRelativeTime } from '../../utils/time'

interface RelativeTimeProps {
  date: string | Date | null | undefined
  className?: string
}

function toIso(value: string | Date | null | undefined): string | null {
  if (!value) {
    return null
  }
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value.toISOString()
  }
  return value
}

function formatExact(value: string | Date | null | undefined, locale: string): string {
  if (!value) {
    return '—'
  }
  const parsed = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return typeof value === 'string' ? value : '—'
  }
  return new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(parsed)
}

/**
 * Relative timestamp with a branded hover/focus tooltip.
 *
 * The visible label stays short ("3 ч. назад"); the exact local time is only
 * shown in the custom tooltip, so the browser's default `title` bubble never
 * appears. Works in light and dark M3 themes.
 */
export default function RelativeTime({ date, className }: RelativeTimeProps) {
  const { locale } = useI18n()
  const tooltipId = useId()
  const iso = toIso(date)
  const relative = formatRelativeTime(iso, locale)
  const exact = formatExact(date, locale)

  if (!date) {
    return <span className={className}>—</span>
  }

  return (
    <span
      className={`group relative inline-flex focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
        className ?? ''
      }`}
      tabIndex={0}
      aria-describedby={tooltipId}
    >
      <span>{relative}</span>
      <span
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-0 z-50 mb-1.5 whitespace-nowrap rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[11px] font-medium text-white opacity-0 shadow-lg transition-opacity duration-150 group-hover:visible group-hover:opacity-100 group-focus-visible:visible group-focus-visible:opacity-100 dark:border-outline-variant dark:bg-surface-container dark:text-on-surface"
      >
        {exact}
      </span>
    </span>
  )
}
