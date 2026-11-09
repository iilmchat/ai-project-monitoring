import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { scan, updateSettings } from '../api/client'
import { LanguageProvider } from '../i18n'
import Onboarding from './Onboarding'

vi.mock('../api/client', () => ({
  scan: vi.fn(),
  updateSettings: vi.fn(),
}))

function renderOnboarding() {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={['/onboarding']}>
        <Routes>
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/" element={<p>dashboard</p>} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('Onboarding', () => {
  beforeEach(() => {
    window.localStorage.setItem('iiruchating.locale', 'ru')
    vi.clearAllMocks()
    vi.mocked(updateSettings).mockResolvedValue({} as never)
    vi.mocked(scan).mockResolvedValue({
      scan_id: 1,
      started_at: '2026-01-01T00:00:00Z',
    })
  })

  it('renders the welcome step first', () => {
    renderOnboarding()

    expect(
      screen.getByRole('heading', {
        name: 'Добро пожаловать в IIRuchating!',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Начать' })).toBeInTheDocument()
  })

  it('moves through the folder and token steps', async () => {
    const user = userEvent.setup()
    renderOnboarding()

    await user.click(screen.getByRole('button', { name: 'Начать' }))
    expect(
      screen.getByRole('heading', { name: 'Папка для сканирования' }),
    ).toBeInTheDocument()

    const next = screen.getByRole('button', { name: 'Далее' })
    expect(next).toBeDisabled()

    // Browser mode: a plain text input is shown instead of the Tauri dialog.
    await user.type(screen.getByLabelText('Путь к папке'), 'C:\\Projects')
    expect(next).toBeEnabled()
    await user.click(next)

    expect(
      screen.getByRole('heading', { name: 'Токены доступа' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('GitHub token')).toBeInTheDocument()
    expect(screen.getByLabelText('GitFlic token')).toBeInTheDocument()
  })

  it('saves the scan root and starts the first scan', async () => {
    const user = userEvent.setup()
    renderOnboarding()

    await user.click(screen.getByRole('button', { name: 'Начать' }))
    await user.type(screen.getByLabelText('Путь к папке'), 'C:\\Projects')
    await user.click(screen.getByRole('button', { name: 'Далее' }))
    await user.click(
      screen.getByRole('button', { name: 'Сохранить и продолжить' }),
    )

    await waitFor(() => {
      expect(updateSettings).toHaveBeenCalledWith({ scan_roots: 'C:\\Projects' })
    })
    expect(scan).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('dashboard')).toBeInTheDocument()
  })

  it('allows skipping optional tokens', async () => {
    const user = userEvent.setup()
    renderOnboarding()

    await user.click(screen.getByRole('button', { name: 'Начать' }))
    await user.type(screen.getByLabelText('Путь к папке'), '/srv/repos')
    await user.click(screen.getByRole('button', { name: 'Далее' }))
    await user.type(screen.getByLabelText('GitHub token'), 'ghp_secret')
    await user.click(screen.getByRole('button', { name: 'Пропустить' }))

    await waitFor(() => {
      expect(updateSettings).toHaveBeenCalledWith({ scan_roots: '/srv/repos' })
    })
  })
})
