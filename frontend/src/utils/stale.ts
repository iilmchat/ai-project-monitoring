import type { RepositoryStatus } from '../api/types'

const STALE_AFTER_MS = 10 * 60 * 1000

export function isStatusStale(status: RepositoryStatus | null | undefined): boolean {
  if (!status) {
    return false
  }
  if (status.remote_status === 'stale' || status.remote_status === 'unavailable') {
    return true
  }
  const checked = new Date(status.checked_at).getTime()
  if (Number.isNaN(checked)) {
    return false
  }
  return Date.now() - checked > STALE_AFTER_MS
}
