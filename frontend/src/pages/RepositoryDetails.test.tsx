import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getActions, getLog, getMirror, getRecommendations, getRepositories, getStatus } from '../api/client'
import type { DashboardRepository, MirrorStatus, RepositoryStatus } from '../api/types'
import RepositoryDetails from './RepositoryDetails'

vi.mock('../api/client', () => ({
  getActions: vi.fn(),
  getLog: vi.fn(),
  getMirror: vi.fn(),
  getRecommendations: vi.fn(),
  getRepositories: vi.fn(),
  getStatus: vi.fn(),
  refreshMirror: vi.fn(),
  refreshRepository: vi.fn(),
  runAction: vi.fn(),
  runMirrorAction: vi.fn(),
  updateMirrorPolicy: vi.fn(),
}))

const status: RepositoryStatus = {
  repository_id: 1,
  path: 'C:/work/app',
  branch: 'main',
  head_sha: 'abc123',
  head_subject: 'init',
  head_date: '2026-11-05T10:00:00Z',
  upstream: 'origin/main',
  ahead: 0,
  behind: 0,
  state: 'dirty',
  dirty: { modified: 1, staged: 0, untracked: 0, conflicted: 0 },
  detached: false,
  remote_status: 'stale',
  error: null,
  checked_at: '2026-11-05T10:00:00Z',
}

const repository: DashboardRepository = {
  id: 1,
  path: 'C:/work/app',
  alias: 'app',
  tracked: true,
  github_full_name: 'acme/app',
  gitflic_full_name: 'acme/app',
  canonical_provider: 'github',
  mirror_expected: true,
  mirror_policy: 'github_to_gitflic',
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
  status,
  mirror: null,
}

const mirror: MirrorStatus = {
  repository_id: 1,
  github: null,
  gitflic: null,
  mirror_status: 'unavailable',
  canonical_provider: 'github',
  mirror_expected: true,
  recommendations: [],
  checked_at: '2026-11-05T10:00:00Z',
}

function renderDetails() {
  return render(
    <MemoryRouter initialEntries={['/repo/1']}>
      <Routes>
        <Route path="/repo/:id" element={<RepositoryDetails />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RepositoryDetails actions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRepositories).mockResolvedValue({
      items: [repository],
      total: 1,
      skip: 0,
      limit: 500,
    })
    vi.mocked(getStatus).mockResolvedValue(status)
    vi.mocked(getLog).mockResolvedValue([])
    vi.mocked(getRecommendations).mockResolvedValue([
      {
        action: 'stash',
        reason: 'Есть незакоммиченные изменения.',
        command: 'git stash',
        category: 'local',
      },
    ])
    vi.mocked(getMirror).mockResolvedValue(mirror)
    vi.mocked(getActions).mockResolvedValue([])
  })

  it('opens the confirmation modal from a recommendation', async () => {
    const user = userEvent.setup()
    renderDetails()

    const execute = await screen.findByRole('button', { name: 'Выполнить' })
    await user.click(execute)

    expect(screen.getByText('Подтверждение действия')).toBeInTheDocument()
    expect(
      screen.getByText(/Я понимаю, что действие изменит репозиторий/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отмена' })).toBeInTheDocument()
  })
})
