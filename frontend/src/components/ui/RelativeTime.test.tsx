import { render, screen } from '@testing-library/react'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'

import { LanguageProvider } from '../../i18n'
import RelativeTime from './RelativeTime'

function renderTime(date: string | Date | null) {
  window.localStorage.setItem('iiruchating.locale', 'ru')
  return render(
    <LanguageProvider>
      <RelativeTime date={date} />
    </LanguageProvider>,
  )
}

describe('RelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 10, 11, 18, 4, 31))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders a relative label with a custom tooltip instead of a title', () => {
    renderTime(new Date(2026, 10, 11, 18, 1, 31))

    const label = screen.getByText('3 мин. назад')
    expect(label).toBeInTheDocument()

    const tooltip = screen.getByRole('tooltip')
    expect(tooltip).toHaveTextContent('2026')
    expect(tooltip).toHaveTextContent('18:01:31')
    expect(label.closest('[title]')).toBeNull()
  })

  it('renders an empty placeholder for a missing date', () => {
    renderTime(null)

    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})
