import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import LanguageToggle from './LanguageToggle'
import { LanguageProvider, useI18n } from '../i18n'

function Harness() {
  const { t } = useI18n()
  return (
    <div>
      <LanguageToggle />
      <p>{t('nav.dashboard')}</p>
    </div>
  )
}

describe('LanguageToggle', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.localStorage.setItem('iiruchating.locale', 'ru')
    document.documentElement.lang = 'ru'
  })

  it('switches RU/EN, persists the choice and updates document.lang', async () => {
    const user = userEvent.setup()
    render(
      <LanguageProvider>
        <Harness />
      </LanguageProvider>,
    )

    expect(screen.getByText('Дашборд')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'EN' }))

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(window.localStorage.getItem('iiruchating.locale')).toBe('en')
    expect(document.documentElement.lang).toBe('en')

    await user.click(screen.getByRole('button', { name: 'RU' }))

    expect(screen.getByText('Дашборд')).toBeInTheDocument()
    expect(window.localStorage.getItem('iiruchating.locale')).toBe('ru')
  })
})
