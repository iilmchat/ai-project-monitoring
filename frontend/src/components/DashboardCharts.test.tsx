import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { CSSProperties, ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { DashboardSummary } from '../api/types'
import { ThemeProvider, useTheme } from '../theme/ThemeContext'
import DashboardCharts from './DashboardCharts'

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  PieChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Pie: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Cell: ({ fill }: { fill?: string }) => <span data-testid="cell" data-fill={fill} />,
  Tooltip: () => null,
  Legend: ({ wrapperStyle }: { wrapperStyle?: CSSProperties }) => (
    <div data-testid="legend" data-color={wrapperStyle?.color} />
  ),
  BarChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Bar: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  XAxis: ({
    stroke,
    tick,
  }: {
    stroke?: string
    tick?: { fill?: string }
  }) => <div data-testid="x-axis" data-stroke={stroke} data-fill={tick?.fill} />,
  YAxis: ({
    stroke,
    tick,
  }: {
    stroke?: string
    tick?: { fill?: string }
  }) => <div data-testid="y-axis" data-stroke={stroke} data-fill={tick?.fill} />,
  CartesianGrid: ({ stroke }: { stroke?: string }) => (
    <div data-testid="grid" data-stroke={stroke} />
  ),
}))

const summary: DashboardSummary = {
  total: 3,
  clean: 2,
  needs_attention: 1,
  untracked: 0,
  stale: 0,
  errors: 0,
  mirror_issues: 1,
  by_state: { current: 2, dirty: 1 },
  by_mirror_status: { in_sync: 2, behind_gitflic: 1 },
}

function Harness() {
  const { toggle } = useTheme()
  return (
    <>
      <button type="button" onClick={toggle}>
        toggle
      </button>
      <DashboardCharts summary={summary} />
    </>
  )
}

describe('DashboardCharts theme', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('uses M3 light colours and switches to dark without remounting', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <Harness />
      </ThemeProvider>,
    )

    expect(await screen.findByTestId('grid')).toHaveAttribute('data-stroke', '#1D1A23')
    expect(screen.getByTestId('x-axis')).toHaveAttribute('data-fill', '#1D1A23')
    expect(screen.getByTestId('y-axis')).toHaveAttribute('data-fill', '#1D1A23')
    expect(screen.getAllByTestId('legend')[0]).toHaveAttribute('data-color', '#1D1A23')

    await user.click(screen.getByRole('button', { name: 'toggle' }))

    expect(screen.getByTestId('grid')).toHaveAttribute('data-stroke', '#FFFFFF')
    expect(screen.getByTestId('x-axis')).toHaveAttribute('data-fill', '#FFFFFF')
    expect(screen.getByTestId('y-axis')).toHaveAttribute('data-fill', '#FFFFFF')
    expect(screen.getAllByTestId('legend')[0]).toHaveAttribute('data-color', '#FFFFFF')
  })
})
