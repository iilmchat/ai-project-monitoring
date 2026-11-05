import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getDashboard } from '../api/client'
import type { DashboardResponse, RepositoryStatus } from '../api/types'
import Dashboard from './Dashboard'

vi.mock('../api/client', () => ({
  bulkFetchAll: vi.fn(),
  bulkSyncMirrorsAll: vi.fn(),
  getDashboard: vi.fn(),
  migrateToGitflic: vi.fn(),
  scan: vi.fn(),
  getScan: vi.fn(),
  trackRepository: vi.fn(),
}))

vi.mock('recharts', () => ({
  ResponsiveContainer: () => <div data-testid="chart-container" />,
  PieChart: () => <div />,
  Pie: () => null,
  Cell: () => null,
  Tooltip: () => null,
  Legend: () => null,
  BarChart: () => <div />,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
}))

const mockedGetDashboard = vi.mocked(getDashboard)

function makeStatus(overrides: Partial<RepositoryStatus>): RepositoryStatus {
  return {
    repository_id: 1,
    path: 'C:/work/repository',
    branch: 'main',
    head_sha: 'abc123',
    head_subject: 'feat: something',
    head_date: '2026-11-05T10:00:00Z',
    upstream: 'origin/main',
    ahead: 0,
    behind: 0,
    state: 'current',
    dirty: { modified: 0, staged: 0, untracked: 0, conflicted: 0 },
    detached: false,
    remote_status: 'ok',
    error: null,
    checked_at: '2026-11-05T10:00:00Z',
    ...overrides,
  }
}

const dashboard: DashboardResponse = {
  summary: {
    total: 2,
    clean: 1,
    needs_attention: 1,
    untracked: 1,
    stale: 0,
    errors: 0,
    mirror_issues: 0,
    by_state: { current: 1, dirty: 1 },
    by_mirror_status: {},
  },
  repositories: [
    {
      id: 1,
      path: 'C:/work/alpha',
      alias: 'alpha',
      tracked: true,
      github_full_name: 'acme/alpha',
      gitflic_full_name: 'acme/alpha',
      canonical_provider: 'github',
      mirror_expected: true,
      mirror_policy: 'github_to_gitflic',
      created_at: '2026-11-01T00:00:00Z',
      updated_at: '2026-11-01T00:00:00Z',
      status: makeStatus({ repository_id: 1, path: 'C:/work/alpha' }),
      mirror: null,
    },
    {
      id: 2,
      path: 'C:/work/beta',
      alias: null,
      tracked: false,
      github_full_name: null,
      gitflic_full_name: null,
      canonical_provider: 'github',
      mirror_expected: true,
      mirror_policy: 'github_to_gitflic',
      created_at: '2026-11-01T00:00:00Z',
      updated_at: '2026-11-01T00:00:00Z',
      status: makeStatus({
        repository_id: 2,
        path: 'C:/work/beta',
        state: 'dirty',
      }),
      mirror: null,
    },
  ],
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  )
}

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedGetDashboard.mockResolvedValue(dashboard)
  })

  it('renders summary cards and repository table', async () => {
    renderDashboard()

    expect(await screen.findByText('alpha')).toBeInTheDocument()
    expect(screen.getByText('beta')).toBeInTheDocument()

    expect(screen.getByTestId('summary-total')).toHaveTextContent('2')
    expect(screen.getByTestId('summary-clean')).toHaveTextContent('1')
    expect(screen.getByTestId('summary-attention')).toHaveTextContent('1')
    expect(screen.getByTestId('summary-untracked')).toHaveTextContent('1')
    expect(await screen.findByTestId('dashboard-charts')).toBeInTheDocument()

    expect(screen.getByRole('columnheader', { name: /Репозиторий/ })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Ahead / Behind' })).toBeInTheDocument()
    expect(screen.getAllByText('current').length).toBeGreaterThan(0)
    expect(screen.getByText('untracked')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отслеживать' })).toBeInTheDocument()
  })

  it('filters repositories by tab', async () => {
    const user = userEvent.setup()
    renderDashboard()

    expect(await screen.findByText('alpha')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Не отслеживаются' }))

    expect(screen.queryByText('alpha')).not.toBeInTheDocument()
    expect(screen.getByText('beta')).toBeInTheDocument()
  })

  it('filters repositories by search query', async () => {
    const user = userEvent.setup()
    renderDashboard()

    expect(await screen.findByText('beta')).toBeInTheDocument()

    await user.type(screen.getByPlaceholderText('Поиск по имени или пути…'), 'alpha')

    expect(screen.getByText('alpha')).toBeInTheDocument()
    expect(screen.queryByText('beta')).not.toBeInTheDocument()
  })
})
