import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { CommitFrequencyPoint } from '../api/types'
import { useTheme } from '../theme/ThemeContext'

const THEMES = {
  light: {
    stroke: '#6B38D4',
    fill: '#6B38D4',
    tooltipBg: '#FEF7FF',
    tooltipBorder: '#CBC3D7',
    text: '#1D1A23',
  },
  dark: {
    stroke: '#C4B5FD',
    fill: '#C4B5FD',
    tooltipBg: '#15121B',
    tooltipBorder: '#494454',
    text: '#FFFFFF',
  },
} as const

/**
 * Lazy-loaded commit-frequency sparkline.
 *
 * recharts lives in this module only, so opening repository details does not
 * pull the whole charting library into the entry/details bundle.
 */
export default function InsightsSparkline({
  data,
}: {
  data: CommitFrequencyPoint[]
}) {
  const { resolved } = useTheme()
  const theme = THEMES[resolved]
  const total = data.reduce((sum, point) => sum + point.count, 0)

  if (data.length === 0 || total === 0) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Нет активности.
      </p>
    )
  }

  return (
    <div data-testid="insights-sparkline" className="h-32 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="insights-area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={theme.fill} stopOpacity={0.35} />
              <stop offset="100%" stopColor={theme.fill} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis dataKey="date" hide />
          <YAxis hide allowDecimals={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: theme.tooltipBg,
              border: `1px solid ${theme.tooltipBorder}`,
              borderRadius: 8,
              color: theme.text,
              fontSize: 12,
            }}
            labelStyle={{ color: theme.text }}
            itemStyle={{ color: theme.text }}
            labelFormatter={(label) => String(label)}
          />
          <Area
            type="monotone"
            dataKey="count"
            stroke={theme.stroke}
            strokeWidth={2}
            fill="url(#insights-area)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
