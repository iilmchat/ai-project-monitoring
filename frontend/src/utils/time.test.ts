import { describe, expect, it } from 'vitest'

import { formatRelativeTime } from './time'

const NOW = new Date('2026-11-11T12:00:00Z').getTime()

describe('formatRelativeTime', () => {
  it('formats recent timestamps in Russian', () => {
    expect(formatRelativeTime('2026-11-11T11:59:40Z', 'ru', NOW)).toBe('только что')
    expect(formatRelativeTime('2026-11-11T11:55:00Z', 'ru', NOW)).toBe('5 мин. назад')
    expect(formatRelativeTime('2026-11-11T10:00:00Z', 'ru', NOW)).toBe('2 ч. назад')
    expect(formatRelativeTime('2026-11-09T12:00:00Z', 'ru', NOW)).toBe('2 дн. назад')
  })

  it('formats timestamps in English', () => {
    expect(formatRelativeTime('2026-11-11T11:59:40Z', 'en', NOW)).toBe('just now')
    expect(formatRelativeTime('2026-11-11T11:55:00Z', 'en', NOW)).toBe('5 min ago')
    expect(formatRelativeTime('2026-11-11T10:00:00Z', 'en', NOW)).toBe('2 h ago')
    expect(formatRelativeTime('2026-11-09T12:00:00Z', 'en', NOW)).toBe('2 d ago')
  })

  it('returns a placeholder for missing values and passes through invalid input', () => {
    expect(formatRelativeTime(null, 'ru', NOW)).toBe('—')
    expect(formatRelativeTime(undefined, 'en', NOW)).toBe('—')
    expect(formatRelativeTime('not-a-date', 'ru', NOW)).toBe('not-a-date')
  })
})
