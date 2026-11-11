const MINUTE_MS = 60 * 1000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

export type RelativeTimeLocale = 'ru' | 'en'

/**
 * Human readable "time ago" label without an external dependency.
 *
 * Used for the dashboard "Проверено" hint; the exact timestamp is shown in a
 * `title` attribute by the caller.
 */
export function formatRelativeTime(
  value: string | null | undefined,
  locale: RelativeTimeLocale = 'ru',
  now: number = Date.now(),
): string {
  if (!value) {
    return '—'
  }
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) {
    return value
  }

  const diff = Math.max(now - timestamp, 0)
  if (diff < MINUTE_MS) {
    return locale === 'ru' ? 'только что' : 'just now'
  }
  if (diff < HOUR_MS) {
    const minutes = Math.floor(diff / MINUTE_MS)
    return locale === 'ru' ? `${minutes} мин. назад` : `${minutes} min ago`
  }
  if (diff < DAY_MS) {
    const hours = Math.floor(diff / HOUR_MS)
    return locale === 'ru' ? `${hours} ч. назад` : `${hours} h ago`
  }
  const days = Math.floor(diff / DAY_MS)
  return locale === 'ru' ? `${days} дн. назад` : `${days} d ago`
}
