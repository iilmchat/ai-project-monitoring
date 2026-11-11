import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  bulkFetchAll,
  getDashboard,
  getDashboardAdvice,
  getGlobalDependencies,
  getGlobalStats,
  getHeatmap,
  getRepositories,
  getUnificationAdvice,
} from '../api/client'
import type { DashboardResponse, RepositoryStatus } from '../api/types'
import { useTableStore } from '../store/useTableStore'
import { ThemeProvider } from '../theme/ThemeContext'
import Dashboard from './Dashboard'

vi.mock('../api/client', () => ({
  bulkFetchAll: vi.fn(),
  bulkSyncMirrorsAll: vi.fn(),
  exportRepositories: vi.fn(),
  getDashboard: vi.fn(),
  getDashboardAdvice: vi.fn(),
  getGlobalDependencies: vi.fn(),
  getGlobalStats: vi.fn(),
  getGlobalStatsAdvice: vi.fn(),
  getHeatmap: vi.fn(),
  getRepositories: vi.fn(),
  getUnificationAdvice: vi.fn(),
  migrateToGitflic: vi.fn(),
  runAction: vi.fn(),
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
    <ThemeProvider>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('Dashboard', () => {
  let writeText: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    window.localStorage.clear()
    useTableStore.setState({
      selectedRepoIds: [],
      visibleColumns: {
        branch: true,
        status: true,
        mirror: true,
        aheadBehind: true,
        ci: true,
      },
      columnWidths: {
        branch: 110,
        status: 120,
        mirror: 150,
        aheadBehind: 120,
        ci: 90,
      },
    })
    vi.mocked(getDashboard).mockResolvedValue(dashboard)
    vi.mocked(getRepositories).mockResolvedValue({
      items: dashboard.repositories,
      total: dashboard.repositories.length,
      skip: 0,
      limit: 500,
    })
    vi.mocked(getHeatmap).mockResolvedValue({})
    vi.mocked(getGlobalDependencies).mockResolvedValue({
      checked_at: '2026-11-06T10:00:00Z',
      ecosystems: { python: [], node: [] },
      summary: { repositories: 0, packages: 0, unification_candidates: 0 },
      error: null,
    })
    vi.mocked(getGlobalStats).mockResolvedValue({
      checked_at: '2026-11-11T12:00:00Z',
      cached: false,
      scope: { repositories: 0, tracked: 0, scanned: 0, skipped: 0 },
      summary: {
        outdated_packages: 0,
        unique_outdated_packages: 0,
        vulnerabilities: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0,
          unknown: 0,
          total: 0,
          unique_cves: 0,
        },
        dirty_files: 0,
        diverged_branches: 0,
        iac_issues: 0,
        problem_types: [],
      },
      repositories: [],
      top_problematic: [],
      errors: [],
      error: null,
    })
  })

  it('renders summary cards and repository table', async () => {
    renderDashboard()

    expect(await screen.findByText('alpha')).toBeInTheDocument()
    expect(screen.getByText('beta')).toBeInTheDocument()

    expect(screen.getByTestId('summary-total')).toHaveTextContent('2')
    expect(screen.getByTestId('summary-clean')).toHaveTextContent('1')
    expect(screen.getByTestId('summary-attention')).toHaveTextContent('1')
    expect(screen.getByTestId('summary-untracked')).toHaveTextContent('1')

    await userEvent.setup().click(screen.getByRole('button', { name: 'Показать аналитику' }))
    expect(await screen.findByTestId('dashboard-charts')).toBeInTheDocument()

    expect(screen.getByRole('columnheader', { name: /Репозиторий/ })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Впереди / Позади' })).toBeInTheDocument()
    expect(screen.getAllByText('чистый').length).toBeGreaterThan(0)
    expect(screen.getByText('не отслеживается')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отслеживать' })).toBeInTheDocument()
  })

  it('renders AI digest after clicking generate', async () => {
    vi.mocked(getDashboardAdvice).mockResolvedValue({
      advice: 'Начните с dirty-репозиториев.',
      cached: false,
      model: 'fake',
      generated_at: '2026-11-08T10:00:00Z',
      stats: { dirty: 1 },
    })
    const user = userEvent.setup()
    renderDashboard()

    await user.click(await screen.findByRole('button', { name: 'Сгенерировать' }))

    expect(await screen.findByText('Начните с dirty-репозиториев.')).toBeInTheDocument()
  })

  it('filters repositories by tab', async () => {
    const user = userEvent.setup()
    renderDashboard()

    expect(await screen.findByText('alpha')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Фильтры/ }))
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

  it('selects rows and scopes bulk fetch to selection', async () => {
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('alpha')
    await user.click(screen.getByRole('checkbox', { name: 'Выбрать alpha' }))

    const fetchSelected = screen.getByRole('button', { name: 'Обновить выбранные (1)' })
    expect(fetchSelected).toBeInTheDocument()

    await user.click(fetchSelected)
    expect(bulkFetchAll).toHaveBeenCalledWith([1])
  })

  it('opens a context menu on right click', async () => {
    renderDashboard()

    const alpha = await screen.findByText('alpha')
    const row = alpha.closest('tr')
    expect(row).not.toBeNull()
    fireEvent.contextMenu(row as HTMLTableRowElement, { clientX: 20, clientY: 20 })

    expect(
      await screen.findByRole('menuitem', { name: 'Скопировать путь' }),
    ).toBeInTheDocument()
  })

  it('supports Space to select a focused table row', async () => {
    renderDashboard()

    const alpha = await screen.findByText('alpha')
    const row = alpha.closest('tr') as HTMLTableRowElement
    row.focus()
    await waitFor(() => {
      expect(row.className).toContain('ring-primary')
    })
    fireEvent.keyDown(row, { key: ' ', code: 'Space' })

    expect(await screen.findByRole('button', { name: 'Обновить выбранные (1)' })).toBeInTheDocument()
  })

  it('applies filters from URL search params', async () => {    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/?status=dirty']}>
          <Dashboard />
        </MemoryRouter>
      </ThemeProvider>,
    )

    expect(await screen.findByText('beta')).toBeInTheDocument()
    expect(screen.queryByText('alpha')).not.toBeInTheDocument()

    await userEvent.setup().click(screen.getByRole('button', { name: /Фильтры/ }))
    expect(screen.getByRole('button', { name: 'есть изменения' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('copies the visible dashboard summary as Markdown', async () => {
    renderDashboard()

    await screen.findByText('alpha')
    fireEvent.click(screen.getByRole('button', { name: 'Скопировать сводку' }))

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1))
    const markdown = String(writeText.mock.calls[0][0])
    expect(markdown).toContain('## IIRuchating Summary (')
    expect(markdown).toContain('- Всего репозиториев: 2')
    expect(markdown).toContain('- Требуют внимания: 1')
    expect(markdown).toContain('- **beta** (`C:/work/beta`): dirty')
    expect(screen.getByText('Сводка скопирована')).toBeInTheDocument()
  })

  it('renders global dependency aggregation with unification badge', async () => {
    vi.mocked(getGlobalDependencies).mockResolvedValue({
      checked_at: '2026-11-06T10:00:00Z',
      ecosystems: {
        python: [
          {
            name: 'fastapi',
            latest_version: '0.116.0',
            distribution: [
              { version: '0.110.0', projects: ['alpha'] },
              { version: '0.115.0', projects: ['beta'] },
            ],
            versions_count: 2,
            projects_count: 2,
            unification_needed: true,
          },
        ],
        node: [],
      },
      summary: { repositories: 2, packages: 1, unification_candidates: 1 },
      error: null,
    })

    renderDashboard()

    await userEvent.setup().click(screen.getByRole('button', { name: 'Показать аналитику' }))
    expect(await screen.findByTestId('global-dependencies')).toBeInTheDocument()
    expect(await screen.findByText('fastapi')).toBeInTheDocument()
    expect(screen.getByText('Унифицировать')).toBeInTheDocument()
    expect(screen.getByText('0.116.0')).toBeInTheDocument()

    vi.mocked(getUnificationAdvice).mockResolvedValue({
      ecosystem: 'python',
      package: 'fastapi',
      advice: 'Унифицируйтесь на 0.116.0.',
      cached: false,
      model: 'fake',
      generated_at: '2026-11-08T10:00:00Z',
    })
    await userEvent.setup().click(screen.getByRole('button', { name: 'AI Совет' }))
    expect(await screen.findByText('Унифицируйтесь на 0.116.0.')).toBeInTheDocument()

    await userEvent.setup().click(screen.getByRole('button', { name: /Python/ }))
    expect(screen.getByText('fastapi')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: /Node/ }))
    expect(screen.queryByText('fastapi')).not.toBeInTheDocument()
  })
})
