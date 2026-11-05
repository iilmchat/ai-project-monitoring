import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  getDashboard,
  getScan,
  scan,
  trackRepository,
} from '../api/client'
import type { DashboardRepository, DashboardResponse } from '../api/types'
import StatusBadge from '../components/StatusBadge'

type Filter = 'all' | 'attention' | 'untracked'

const ATTENTION_STATES = new Set(['dirty', 'ahead', 'behind', 'diverged', 'no_upstream'])

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'attention', label: 'Требуют внимания' },
  { id: 'untracked', label: 'Не отслеживаются' },
]

function displayName(repository: DashboardRepository): string {
  if (repository.alias) {
    return repository.alias
  }
  const normalized = repository.path.replaceAll('\\', '/')
  return normalized.split('/').filter(Boolean).pop() ?? repository.path
}

function needsAttention(repository: DashboardRepository): boolean {
  const state = repository.status?.state
  return state !== undefined && ATTENTION_STATES.has(state)
}

export default function Dashboard() {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [busyRepository, setBusyRepository] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function loadDashboard() {
    setLoading(true)
    try {
      setDashboard(await getDashboard())
      setError(null)
    } catch {
      setError('Не удалось загрузить дашборд. Проверьте, запущен ли backend.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    void (async () => {
      try {
        const data = await getDashboard()
        if (!active) {
          return
        }
        setDashboard(data)
        setError(null)
      } catch {
        if (active) {
          setError('Не удалось загрузить дашборд. Проверьте, запущен ли backend.')
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    })()
    return () => {
      active = false
    }
  }, [])

  async function handleScan() {
    setScanning(true)
    setError(null)
    try {
      const started = await scan()
      let status = await getScan(started.scan_id)
      let attempts = 0
      while ((status.status === 'pending' || status.status === 'running') && attempts < 40) {
        await new Promise((resolve) => setTimeout(resolve, 750))
        status = await getScan(started.scan_id)
        attempts += 1
      }
      await loadDashboard()
    } catch {
      setError('Сканирование не удалось.')
    } finally {
      setScanning(false)
    }
  }

  async function handleTrack(repositoryId: number) {
    setBusyRepository(repositoryId)
    try {
      await trackRepository(repositoryId)
      await loadDashboard()
    } catch {
      setError('Не удалось обновить список отслеживаемых репозиториев.')
    } finally {
      setBusyRepository(null)
    }
  }

  const repositories = useMemo(() => {
    if (!dashboard) {
      return []
    }
    if (filter === 'attention') {
      return dashboard.repositories.filter(needsAttention)
    }
    if (filter === 'untracked') {
      return dashboard.repositories.filter((repository) => !repository.tracked)
    }
    return dashboard.repositories
  }, [dashboard, filter])

  const summary = dashboard?.summary

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Дашборд</h1>
          <p className="text-sm text-slate-500">
            Локальное состояние репозиториев и расхождения с remote.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleScan()}
          disabled={scanning}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {scanning ? 'Сканирование…' : 'Сканировать'}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <SummaryCard label="Всего" value={summary?.total ?? 0} testId="summary-total" />
        <SummaryCard label="Чистые" value={summary?.clean ?? 0} testId="summary-clean" />
        <SummaryCard
          label="Требуют внимания"
          value={summary?.needs_attention ?? 0}
          testId="summary-attention"
        />
        <SummaryCard
          label="Не отслеживаются"
          value={summary?.untracked ?? 0}
          testId="summary-untracked"
        />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setFilter(item.id)}
                className={`rounded-full px-3 py-1 text-sm font-medium transition ${
                  filter === item.id
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <span className="text-xs text-slate-500">{repositories.length} репозиториев</span>
        </div>

        {loading ? (
          <p className="px-4 py-8 text-center text-sm text-slate-500">Загрузка…</p>
        ) : repositories.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-slate-500">
            Нет репозиториев. Запустите сканирование.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Репозиторий</th>
                  <th className="px-4 py-3 font-medium">Ветка</th>
                  <th className="px-4 py-3 font-medium">Статус</th>
                  <th className="px-4 py-3 font-medium">Ahead / Behind</th>
                  <th className="px-4 py-3 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {repositories.map((repository) => (
                  <tr key={repository.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/repo/${repository.id}`}
                        className="font-medium text-slate-900 hover:text-blue-700"
                      >
                        {displayName(repository)}
                      </Link>
                      <p className="max-w-xs truncate text-xs text-slate-500" title={repository.path}>
                        {repository.path}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {repository.status?.branch ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge state={repository.status?.state} tracked={repository.tracked} />
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {repository.status
                        ? `↑${repository.status.ahead} ↓${repository.status.behind}`
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {repository.tracked ? (
                        <Link
                          to={`/repo/${repository.id}`}
                          className="text-sm font-medium text-blue-700 hover:underline"
                        >
                          Детали
                        </Link>
                      ) : (
                        <button
                          type="button"
                          onClick={() => void handleTrack(repository.id)}
                          disabled={busyRepository === repository.id}
                          className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60"
                        >
                          {busyRepository === repository.id ? '…' : 'Отслеживать'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}

function SummaryCard({
  label,
  value,
  testId,
}: {
  label: string
  value: number
  testId: string
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-900" data-testid={testId}>
        {value}
      </p>
    </div>
  )
}
