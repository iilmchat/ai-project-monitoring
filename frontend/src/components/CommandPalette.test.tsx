import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { bulkFetchAll, getDashboard } from '../api/client'
import type { DashboardResponse } from '../api/types'
import CommandPalette from './CommandPalette'

vi.mock('../api/client', () => ({
  bulkFetchAll: vi.fn(),
  getDashboard: vi.fn(),
  migrateToGitflic: vi.fn(),
  scan: vi.fn(),
}))

const dashboard: DashboardResponse = {
  summary: {
    total: 1,
    clean: 1,
    needs_attention: 0,
    untracked: 0,
    stale: 0,
    errors: 0,
    mirror_issues: 0,
    by_state: { current: 1 },
    by_mirror_status: {},
  },
  repositories: [
    {
      id: 7,
      path: 'C:/work/alpha',
      alias: 'alpha',
      tracked: true,
      github_full_name: null,
      gitflic_full_name: null,
      canonical_provider: 'github',
      mirror_expected: true,
      mirror_policy: 'github_to_gitflic',
      created_at: '2026-11-01T00:00:00Z',
      updated_at: '2026-11-01T00:00:00Z',
      status: null,
      mirror: null,
    },
  ],
}

describe('CommandPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getDashboard).mockResolvedValue(dashboard)
  })

  it('finds repositories and pages', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <CommandPalette open onClose={vi.fn()} />
      </MemoryRouter>,
    )

    expect(await screen.findByText('alpha')).toBeInTheDocument()
    expect(screen.getByText('Репозитории')).toBeInTheDocument()
    expect(screen.getByText('Страницы')).toBeInTheDocument()

    await user.type(
      screen.getByPlaceholderText('Поиск репозиториев, страниц и действий…'),
      'настрой',
    )
    expect(screen.getByText('Настройки')).toBeInTheDocument()
    expect(screen.queryByText('alpha')).not.toBeInTheDocument()
  })

  it('runs the Fetch All action', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <MemoryRouter>
        <CommandPalette open onClose={onClose} />
      </MemoryRouter>,
    )

    await screen.findByText('alpha')
    await user.type(
      screen.getByPlaceholderText('Поиск репозиториев, страниц и действий…'),
      'fetch all',
    )
    await user.click(screen.getByText('Fetch All'))

    await waitFor(() => {
      expect(bulkFetchAll).toHaveBeenCalled()
    })
    expect(onClose).toHaveBeenCalled()
  })
})
