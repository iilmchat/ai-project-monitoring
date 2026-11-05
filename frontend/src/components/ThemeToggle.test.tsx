import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import ThemeToggle from '../components/ThemeToggle'
import { ThemeProvider } from '../theme/ThemeContext'

describe('ThemeToggle', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('toggles the dark class on <html>', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    )

    expect(document.documentElement.classList.contains('dark')).toBe(false)

    await user.click(screen.getByRole('button', { name: 'Переключить тему' }))
    await waitFor(() => {
      expect(document.documentElement.classList.contains('dark')).toBe(true)
    })

    await user.click(screen.getByRole('button', { name: 'Переключить тему' }))
    await waitFor(() => {
      expect(document.documentElement.classList.contains('dark')).toBe(false)
    })
    expect(window.localStorage.getItem('theme')).toBe('light')
  })
})
