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

interface TooltipPayloadItem {
  name?: string
  value?: number
  payload?: { name?: string; value?: number }
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: TooltipPayloadItem[]
}) {
  if (!active || !payload?.length) {
    return null
  }
  const item = payload[0]
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
      {item.payload?.name ?? item.name}: {item.payload?.value ?? item.value}
    </div>
  )
}

export default function DashboardCharts({ summary }: { summary: DashboardSummary }) {
  const stateData = [
    ...Object.entries(summary.by_state).map(([name, value]) => ({ name, value })),
    { name: 'untracked', value: summary.untracked },
  ].filter((item) => item.value > 0)

  const mirrorData = Object.entries(summary.by_mirror_status)
    .map(([name, value]) => ({ name, value }))
    .filter((item) => item.value > 0)

  return (
    <div data-testid="dashboard-charts" className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Обзор состояния
        </h2>
        <div className="mt-3 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={stateData} dataKey="value" nameKey="name" outerRadius="80%">
                {stateData.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={STATE_COLORS[entry.name] ?? '#8B5CF6'}
                  />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Состояние зеркал
        </h2>
        <div className="mt-3 h-64">
          {mirrorData.length === 0 ? (
            <p className="pt-16 text-center text-sm text-slate-500 dark:text-slate-400">
              Нет данных о зеркалах.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={mirrorData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#94A3B8" opacity={0.3} />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-15} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {mirrorData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={MIRROR_COLORS[entry.name] ?? '#8B5CF6'}
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
