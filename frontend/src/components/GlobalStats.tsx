import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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

import { getGlobalStats, getGlobalStatsAdvice } from '../api/client'
import type {
  GlobalStatsAdvice,
  GlobalStatsReport,
  ProblemTypeSummary,
} from '../api/types'
import { useI18n } from '../i18n'
import { useTheme } from '../theme/ThemeContext'
import MarkdownView from './MarkdownView'

const PROBLEM_COLORS: Record<string, string> = {
  outdated_packages: '#F59E0B',
  vulnerabilities: '#EF4444',
  dirty_files: '#0EA5E9',
  diverged_branches: '#8B5CF6',
  iac_issues: '#10B981',
}

const DEFAULT_COLOR = '#8B5CF6'

const CHART_THEMES = {
  light: {
    surface: '#FEF7FF',
    onSurface: '#1D1A23',
    grid: '#1D1A23',
    border: '#CBC3D7',
  },
  dark: {
    surface: '#15121B',
    onSurface: '#FFFFFF',
    grid: '#FFFFFF',
    border: '#494454',
  },
} as const

interface ProblemDatum {
  key: string
  label: string
  value: number
}

interface TopDatum {
  repositoryId: number
  name: string
  score: number
}

function problemLabel(
  item: ProblemTypeSummary,
  t: ReturnType<typeof useI18n>['t'],
): string {
  switch (item.type) {
    case 'outdated_packages':
      return t('dashboard.globalStats.problem.outdated_packages')
    case 'vulnerabilities':
      return t('dashboard.globalStats.problem.vulnerabilities')
    case 'dirty_files':
      return t('dashboard.globalStats.problem.dirty_files')
    case 'diverged_branches':
      return t('dashboard.globalStats.problem.diverged_branches')
    case 'iac_issues':
      return t('dashboard.globalStats.problem.iac_issues')
    default:
      return item.type
  }
}

export default function GlobalStats() {
  const { t, locale, formatNumber } = useI18n()
  const { resolved } = useTheme()
  const navigate = useNavigate()
  const theme = CHART_THEMES[resolved]

  const [report, setReport] = useState<GlobalStatsReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [advice, setAdvice] = useState<GlobalStatsAdvice | null>(null)
  const [adviceLoading, setAdviceLoading] = useState(false)
  const [adviceError, setAdviceError] = useState<string | null>(null)

  async function load(refresh = false, silent = false) {
    if (refresh) {
      setRefreshing(true)
    } else if (!silent) {
      setLoading(true)
    }
    try {
      setReport(await getGlobalStats(refresh))
      setError(null)
    } catch {
      setError(t('dashboard.globalStats.loadError'))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    let active = true
    void getGlobalStats()
      .then((data) => {
        if (!active) {
          return
        }
        setReport(data)
        setError(null)
      })
      .catch(() => {
        if (active) {
          setError(t('dashboard.globalStats.loadError'))
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [t])

  async function generateAdvice() {
    setAdviceLoading(true)
    setAdviceError(null)
    try {
      setAdvice(await getGlobalStatsAdvice(locale))
    } catch {
      setAdviceError(t('dashboard.globalStats.aiError'))
    } finally {
      setAdviceLoading(false)
    }
  }

  const problemData = useMemo<ProblemDatum[]>(() => {
    if (!report) {
      return []
    }
    return report.summary.problem_types
      .filter((item) => item.count > 0)
      .map((item) => ({
        key: item.type,
        label: problemLabel(item, t),
        value: item.count,
      }))
  }, [report, t])

  const topData = useMemo<TopDatum[]>(() => {
    if (!report) {
      return []
    }
    return report.top_problematic.map((item) => ({
      repositoryId: item.repository_id,
      name: item.name,
      score: item.problem_score,
    }))
  }, [report])

  const totalProblems = problemData.reduce((sum, item) => sum + item.value, 0)
  const isEmpty = totalProblems === 0 && topData.length === 0

  if (loading) {
    return (
      <div
        data-testid="global-stats"
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t('dashboard.globalStats.loading')}
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div
        data-testid="global-stats"
        className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-200"
      >
        {error}
      </div>
    )
  }

  if (!report) {
    return null
  }

  const partial = report.error !== null || report.errors.length > 0
  const highCriticalCves =
    report.summary.vulnerabilities.high + report.summary.vulnerabilities.critical

  return (
    <div
      data-testid="global-stats"
      className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t('dashboard.globalStats.title')}
          </h2>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {t('dashboard.globalStats.hint')}
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {t('dashboard.globalStats.scope', {
              tracked: report.scope.tracked,
              scanned: report.scope.scanned,
              skipped: report.scope.skipped,
            })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {partial && (
            <span
              title={report.errors.join('\n')}
              className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
            >
              {t('dashboard.globalStats.partial')}
            </span>
          )}
          {report.cached && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              {t('dashboard.globalStats.cached')}
            </span>
          )}
          <button
            type="button"
            onClick={() => void load(true)}
            disabled={refreshing}
            className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {refreshing
              ? t('dashboard.globalStats.refreshing')
              : t('dashboard.globalStats.refresh')}
          </button>
        </div>
      </div>

      <div className="space-y-4 p-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <StatCard
            label={t('dashboard.globalStats.outdated')}
            value={report.summary.outdated_packages}
            hint={t('dashboard.globalStats.problem.outdated_packages')}
          />
          <StatCard
            label={t('dashboard.globalStats.cve')}
            value={highCriticalCves}
            hint={`${t('dashboard.globalStats.problem.vulnerabilities')} · ${report.summary.vulnerabilities.total}`}
            tone="danger"
          />
          <StatCard
            label={t('dashboard.globalStats.dirty')}
            value={report.summary.dirty_files}
            hint={t('dashboard.globalStats.showDirty')}
            tone="warning"
            onClick={() => navigate('/?status=dirty')}
          />
          <StatCard
            label={t('dashboard.globalStats.diverged')}
            value={report.summary.diverged_branches}
            hint={t('dashboard.globalStats.showDiverged')}
            tone="violet"
            onClick={() => navigate('/?status=diverged')}
          />
          <StatCard
            label={t('dashboard.globalStats.iac')}
            value={report.summary.iac_issues}
            hint={t('dashboard.globalStats.problem.iac_issues')}
          />
        </div>

        {isEmpty ? (
          <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200">
            {t('dashboard.globalStats.empty')}
          </p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            <div
              className="rounded-lg border p-3"
              style={{ borderColor: theme.border, backgroundColor: theme.surface }}
            >
              <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: theme.onSurface }}>
                {t('dashboard.globalStats.problemsChart')}
              </h3>
              <div
                className="mt-2 h-64"
                role="img"
                aria-label={t('dashboard.globalStats.problemsChart')}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={problemData}
                      dataKey="value"
                      nameKey="label"
                      outerRadius="78%"
                      isAnimationActive={false}
                    >
                      {problemData.map((entry) => (
                        <Cell
                          key={entry.key}
                          fill={PROBLEM_COLORS[entry.key] ?? DEFAULT_COLOR}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: theme.surface,
                        borderColor: theme.border,
                        color: theme.onSurface,
                        fontSize: 12,
                      }}
                    />
                    <Legend
                      wrapperStyle={{ color: theme.onSurface, fontSize: 12 }}
                      formatter={(value: string) => (
                        <span style={{ color: theme.onSurface }}>{value}</span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <p className="sr-only">
                {problemData
                  .map((item) => `${item.label}: ${formatNumber(item.value)}`)
                  .join(', ')}
              </p>
            </div>

            <div
              className="rounded-lg border p-3"
              style={{ borderColor: theme.border, backgroundColor: theme.surface }}
            >
              <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: theme.onSurface }}>
                {t('dashboard.globalStats.topChart')}
              </h3>
              <div
                className="mt-2 h-64"
                role="img"
                aria-label={t('dashboard.globalStats.topChart')}
              >
                {topData.length === 0 ? (
                  <p className="pt-16 text-center text-sm" style={{ color: theme.onSurface }}>
                    {t('dashboard.globalStats.empty')}
                  </p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={topData}>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke={theme.grid}
                        opacity={0.15}
                      />
                      <XAxis
                        dataKey="name"
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
                        contentStyle={{
                          backgroundColor: theme.surface,
                          borderColor: theme.border,
                          color: theme.onSurface,
                          fontSize: 12,
                        }}
                        cursor={{ fill: theme.onSurface, opacity: 0.06 }}
                      />
                      <Bar dataKey="score" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                        {topData.map((entry) => (
                          <Cell key={entry.repositoryId} fill={DEFAULT_COLOR} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
              <ul className="mt-2 space-y-1">
                {topData.map((item) => (
                  <li key={item.repositoryId}>
                    <button
                      type="button"
                      onClick={() => navigate(`/repo/${item.repositoryId}`)}
                      title={t('dashboard.globalStats.openRepository', {
                        name: item.name,
                      })}
                      className="flex w-full items-center justify-between gap-2 rounded px-1.5 py-0.5 text-left text-xs text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      <span className="truncate">{item.name}</span>
                      <span className="font-mono text-[11px] text-slate-400">
                        {formatNumber(item.score)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        <div className="rounded-lg border border-primary/20 p-3 dark:border-primary/30">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-primary">
                {t('dashboard.globalStats.aiHint')}
              </h3>
            </div>
            <div className="flex items-center gap-2">
              {advice?.cached && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                  {t('dashboard.globalStats.aiCached')}
                </span>
              )}
              <button
                type="button"
                onClick={() => void generateAdvice()}
                disabled={adviceLoading}
                className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-container disabled:opacity-60"
              >
                {adviceLoading
                  ? t('dashboard.globalStats.aiLoading')
                  : t('dashboard.globalStats.ai')}
              </button>
            </div>
          </div>
          <div aria-live="polite" className="mt-2">
            {adviceLoading ? (
              <p className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                {t('dashboard.globalStats.aiLoading')}
              </p>
            ) : adviceError ? (
              <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
                {adviceError}
              </p>
            ) : advice ? (
              <MarkdownView content={advice.summary} />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({
  label,
  value,
  hint,
  tone = 'neutral',
  onClick,
}: {
  label: string
  value: number
  hint: string
  tone?: 'neutral' | 'danger' | 'warning' | 'violet'
  onClick?: () => void
}) {
  const { formatNumber } = useI18n()
  const toneClass =
    tone === 'danger'
      ? 'text-red-600 dark:text-red-400'
      : tone === 'warning'
        ? 'text-amber-600 dark:text-amber-400'
        : tone === 'violet'
          ? 'text-primary'
          : 'text-slate-900 dark:text-slate-100'

  const content = (
    <>
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p className={`mt-1 text-2xl font-semibold ${toneClass}`}>
        {formatNumber(value)}
      </p>
      <p className="mt-0.5 text-[11px] text-slate-400 dark:text-slate-500">
        {hint}
      </p>
    </>
  )

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        title={hint}
        className="rounded-lg border border-slate-200 bg-white p-3 text-left shadow-sm transition hover:border-primary/40 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800"
      >
        {content}
      </button>
    )
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      {content}
    </div>
  )
}
