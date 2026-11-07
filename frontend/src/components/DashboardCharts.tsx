import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { DashboardSummary } from '../api/types'
import { mirrorLabel, statusLabel, useI18n } from '../i18n'
import { useTheme } from '../theme/ThemeContext'

/**
 * Brand series colours. They intentionally stay the same in both themes:
 * state semantics must remain recognisable, while axes/grid/tooltip surfaces
 * switch with the M3 theme tokens below.
 */
const STATE_COLORS: Record<string, string> = {
  current: '#10B981',
  dirty: '#F59E0B',
  ahead: '#8B5CF6',
  behind: '#F97316',
  diverged: '#EF4444',
  no_upstream: '#94A3B8',
  detached: '#64748B',
  error: '#DC2626',
  untracked: '#A1A1AA',
}

const MIRROR_COLORS: Record<string, string> = {
  in_sync: '#10B981',
  missing_on_gitflic: '#EF4444',
  missing_on_github: '#EF4444',
  behind_gitflic: '#F59E0B',
  behind_github: '#F59E0B',
  diverged: '#DC2626',
  history_rewritten: '#991B1B',
  not_applicable: '#94A3B8',
  unavailable: '#64748B',
}

const DEFAULT_SERIES_COLOR = '#8B5CF6'

interface ChartTheme {
  surface: string
  onSurface: string
  grid: string
  gridOpacity: number
  tooltipBorder: string
}

const CHART_THEMES: Record<'light' | 'dark', ChartTheme> = {
  light: {
    surface: '#FEF7FF',
    onSurface: '#1D1A23',
    grid: '#1D1A23',
    gridOpacity: 0.12,
    tooltipBorder: '#CBC3D7',
  },
  dark: {
    surface: '#15121B',
    onSurface: '#FFFFFF',
    grid: '#FFFFFF',
    gridOpacity: 0.18,
    tooltipBorder: '#494454',
  },
}

interface TooltipPayloadItem {
  name?: string
  value?: number
  payload?: { key?: string; label?: string; value?: number }
}

function ChartTooltip({
  active,
  payload,
  theme,
}: {
  active?: boolean
  payload?: TooltipPayloadItem[]
  theme: ChartTheme
}) {
  if (!active || !payload?.length) {
    return null
  }
  const item = payload[0]
  return (
    <div
      className="rounded-md border px-3 py-2 text-xs shadow"
      style={{
        backgroundColor: theme.surface,
        borderColor: theme.tooltipBorder,
        color: theme.onSurface,
      }}
    >
      {item.payload?.label ?? item.name}: {item.payload?.value ?? item.value}
    </div>
  )
}

export default function DashboardCharts({ summary }: { summary: DashboardSummary }) {
  const { resolved } = useTheme()
  const { t } = useI18n()
  const theme = CHART_THEMES[resolved]

  const stateData = [
    ...Object.entries(summary.by_state).map(([key, value]) => ({
      key,
      label: statusLabel(key, t),
      value,
    })),
    {
      key: 'untracked',
      label: statusLabel('untracked', t),
      value: summary.untracked,
    },
  ].filter((item) => item.value > 0)

  const mirrorData = Object.entries(summary.by_mirror_status)
    .map(([key, value]) => ({
      key,
      label: mirrorLabel(key, t),
      value,
    }))
    .filter((item) => item.value > 0)

  return (
    <div data-testid="dashboard-charts" className="grid gap-4 lg:grid-cols-2">
      <div
        className="rounded-xl border p-4 shadow-sm"
        style={{ backgroundColor: theme.surface, borderColor: theme.tooltipBorder }}
      >
        <h2
          className="text-sm font-semibold uppercase tracking-wide"
          style={{ color: theme.onSurface }}
        >
          {t('charts.state')}
        </h2>
        <div className="mt-3 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={stateData}
                dataKey="value"
                nameKey="label"
                outerRadius="80%"
                isAnimationActive={false}
              >
                {stateData.map((entry) => (
                  <Cell
                    key={entry.key}
                    fill={STATE_COLORS[entry.key] ?? DEFAULT_SERIES_COLOR}
                  />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip theme={theme} />} />
              <Legend
                wrapperStyle={{ color: theme.onSurface, fontSize: 12 }}
                formatter={(value: string) => (
                  <span style={{ color: theme.onSurface }}>{value}</span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div
        className="rounded-xl border p-4 shadow-sm"
        style={{ backgroundColor: theme.surface, borderColor: theme.tooltipBorder }}
      >
        <h2
          className="text-sm font-semibold uppercase tracking-wide"
          style={{ color: theme.onSurface }}
        >
          {t('charts.mirror')}
        </h2>
        <div className="mt-3 h-64">
          {mirrorData.length === 0 ? (
            <p
              className="pt-16 text-center text-sm"
              style={{ color: theme.onSurface }}
            >
              {t('charts.noMirror')}
            </p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={mirrorData}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke={theme.grid}
                  opacity={theme.gridOpacity}
                />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10, fill: theme.onSurface }}
                  stroke={theme.onSurface}
                  interval={0}
                  angle={-15}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 10, fill: theme.onSurface }}
                  stroke={theme.onSurface}
                />
                <Tooltip
                  content={<ChartTooltip theme={theme} />}
                  cursor={{ fill: theme.onSurface, opacity: 0.06 }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {mirrorData.map((entry) => (
                    <Cell
                      key={entry.key}
                      fill={MIRROR_COLORS[entry.key] ?? DEFAULT_SERIES_COLOR}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  )
}
