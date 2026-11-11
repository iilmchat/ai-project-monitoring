import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getGlobalStats, getGlobalStatsAdvice } from '../api/client'
import type { GlobalStatsReport } from '../api/types'
import { LanguageProvider } from '../i18n'
import { ThemeProvider } from '../theme/ThemeContext'
import GlobalStats from './GlobalStats'

vi.mock('../api/client', () => ({
  getGlobalStats: vi.fn(),
  getGlobalStatsAdvice: vi.fn(),
}))

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  PieChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Pie: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Cell: () => null,
  Tooltip: () => null,
  Legend: ({ formatter }: { formatter?: (value: string) => ReactNode }) => (
    <div>{formatter?.('legend')}</div>
  ),
  BarChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Bar: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
}))

const report: GlobalStatsReport = {
  checked_at: '2026-11-11T12:00:00Z',
  cached: false,
  scope: { repositories: 4, tracked: 3, scanned: 2, skipped: 1 },
  summary: {
    outdated_packages: 12,
    unique_outdated_packages: 9,
    vulnerabilities: {
      critical: 1,
      high: 2,
      medium: 3,
      low: 0,
      unknown: 0,
      total: 6,
      unique_cves: 5,
    },
    dirty_files: 5,
    diverged_branches: 2,
    iac_issues: 0,
    problem_types: [
      { type: 'outdated_packages', count: 12, severity: 'medium' },
      { type: 'vulnerabilities', count: 6, severity: 'high' },
      { type: 'dirty_files', count: 5, severity: 'medium' },
      { type: 'diverged_branches', count: 2, severity: 'high' },
      { type: 'iac_issues', count: 0, severity: 'low' },
    ],
  },
  repositories: [
    {
      repository_id: 7,
      name: 'alpha',
      path: 'C:/projects/alpha',
      status: 'ok',
      stale: false,
      outdated_packages: 8,
      vulnerabilities: {
        critical: 1,
        high: 1,
        medium: 1,
        low: 0,
        unknown: 0,
        total: 3,
        unique_cves: 2,
      },
      dirty_files: 3,
      diverged: true,
      iac_issues: 0,
      problem_score: 47,
      error: null,
    },
    {
      repository_id: 9,
      name: 'beta',
      path: 'C:/projects/beta',
      status: 'partial',
      stale: true,
      outdated_packages: 4,
      vulnerabilities: {
        critical: 0,
        high: 1,
        medium: 2,
        low: 0,
        unknown: 0,
        total: 3,
        unique_cves: 3,
      },
      dirty_files: 2,
      diverged: true,
      iac_issues: 0,
      problem_score: 21,
      error: 'beta: security_unavailable',
    },
  ],
  top_problematic: [
    { repository_id: 7, name: 'alpha', problem_score: 47 },
    { repository_id: 9, name: 'beta', problem_score: 21 },
  ],
  errors: ['beta: security_unavailable'],
  error: 'partial_data',
}

function renderPanel() {
  window.localStorage.setItem('iiruchating.locale', 'ru')
  return render(
    <MemoryRouter>
      <LanguageProvider>
        <ThemeProvider>
          <GlobalStats />
        </ThemeProvider>
      </LanguageProvider>
    </MemoryRouter>,
  )
}

describe('GlobalStats', () => {
  beforeEach(() => {
    vi.mocked(getGlobalStats).mockReset()
    vi.mocked(getGlobalStatsAdvice).mockReset()
  })

  it('renders cards, charts and the partial badge', async () => {
    vi.mocked(getGlobalStats).mockResolvedValue(report)

    renderPanel()

    expect(await screen.findByText('Tech Debt Overview')).toBeInTheDocument()
    expect(
      screen.getByText('Отслеживается: 3 · просканировано: 2 · пропущено: 1'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('Устаревшие пакеты').length).toBeGreaterThan(0)
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('CVE (High/Critical)')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Распределение проблем' })).toBeInTheDocument()
    expect(
      screen.getByRole('img', { name: 'Топ-5 репозиториев по problem_score' }),
    ).toBeInTheDocument()
    expect(screen.getByText('alpha')).toBeInTheDocument()
    expect(screen.getByText('47')).toBeInTheDocument()
    expect(screen.getByText('Часть данных недоступна')).toBeInTheDocument()
  })

  it('shows the empty state when nothing is on fire', async () => {
    vi.mocked(getGlobalStats).mockResolvedValue({
      ...report,
      summary: {
        ...report.summary,
        outdated_packages: 0,
        dirty_files: 0,
        diverged_branches: 0,
        vulnerabilities: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0,
          unknown: 0,
          total: 0,
          unique_cves: 0,
        },
        problem_types: report.summary.problem_types.map((item) => ({
          ...item,
          count: 0,
        })),
      },
      repositories: [],
      top_problematic: [],
      errors: [],
      error: null,
    })

    renderPanel()

    expect(await screen.findByText('Технический долг не найден.')).toBeInTheDocument()
  })

  it('requests the AI report and renders Markdown', async () => {
    const user = userEvent.setup()
    vi.mocked(getGlobalStats).mockResolvedValue(report)
    vi.mocked(getGlobalStatsAdvice).mockResolvedValue({
      generated_at: '2026-11-11T12:01:00Z',
      summary: '# Что горит\n\nНачните с **alpha**.',
      priorities: [],
      model: 'fake-model',
      cached: false,
    })

    renderPanel()

    await user.click(await screen.findByRole('button', { name: 'AI Анализ' }))

    await waitFor(() => expect(getGlobalStatsAdvice).toHaveBeenCalledWith('ru'))
    expect(await screen.findByText('Что горит')).toBeInTheDocument()
    expect(screen.getAllByText('alpha').length).toBeGreaterThan(0)
  })

  it('shows an AI error when the LLM is unavailable', async () => {
    const user = userEvent.setup()
    vi.mocked(getGlobalStats).mockResolvedValue(report)
    vi.mocked(getGlobalStatsAdvice).mockRejectedValue(new Error('503'))

    renderPanel()

    await user.click(await screen.findByRole('button', { name: 'AI Анализ' }))

    expect(
      await screen.findByText('AI недоступен. Проверьте настройки LLM.'),
    ).toBeInTheDocument()
  })
})
