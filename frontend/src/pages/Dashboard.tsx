import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import {
  bulkFetchAll,
  bulkSyncMirrorsAll,
  getDashboard,
  getScan,
  migrateToGitflic,
  runAction,
  scan,
  trackRepository,
} from '../api/client'
import type { DashboardRepository, DashboardResponse } from '../api/types'
import ContextMenu from '../components/ContextMenu'
import MirrorBadge from '../components/MirrorBadge'
import StatusBadge from '../components/StatusBadge'
import { useTableStore } from '../store/useTableStore'
import type { ColumnKey } from '../store/useTableStore'

const DashboardCharts = lazy(() => import('../components/DashboardCharts'))

type Filter = 'all' | 'attention' | 'untracked' | 'mirror'
type SortKey = 'name' | 'status' | 'ahead'
type SortDirection = 'asc' | 'desc'

const ATTENTION_STATES = new Set(['dirty', 'ahead', 'behind', 'diverged', 'no_upstream'])
const MIRROR_OK = new Set(['in_sync', 'not_applicable'])

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'attention', label: 'Требуют внимания' },
  { id: 'untracked', label: 'Не отслеживаются' },
  { id: 'mirror', label: 'Зеркала' },
]

const COLUMN_LABELS: { key: ColumnKey; label: string }[] = [
  { key: 'branch', label: 'Ветка' },
  { key: 'status', label: 'Статус' },
  { key: 'mirror', label: 'Зеркало' },
  { key: 'ci', label: 'CI' },
  { key: 'aheadBehind', label: 'Ahead / Behind' },
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

function hasMirrorIssue(repository: DashboardRepository): boolean {
  const status = repository.mirror?.mirror_status
  return status !== undefined && !MIRROR_OK.has(status)
}

interface ContextState {
  x: number
  y: number
  repository: DashboardRepository
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [busyRepository, setBusyRepository] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const [bulkMessage, setBulkMessage] = useState<string | null>(null)
  const [bulkPolling, setBulkPolling] = useState(false)
  const [columnsOpen, setColumnsOpen] = useState(false)
  const [contextMenu, setContextMenu] = useState<ContextState | null>(null)

  const selectedRepoIds = useTableStore((state) => state.selectedRepoIds)
  const visibleColumns = useTableStore((state) => state.visibleColumns)
  const columnWidths = useTableStore((state) => state.columnWidths)
  const toggleSelected = useTableStore((state) => state.toggleSelected)
  const setSelected = useTableStore((state) => state.setSelected)
  const clearSelected = useTableStore((state) => state.clearSelected)
  const toggleColumn = useTableStore((state) => state.toggleColumn)
  const setColumnWidth = useTableStore((state) => state.setColumnWidth)

  async function loadDashboard(silent = false) {
    if (!silent) {
      setLoading(true)
    }
    try {
      setDashboard(await getDashboard())
      setError(null)
    } catch {
      setError('Не удалось загрузить дашборд. Проверьте, запущен ли backend.')
    } finally {
      if (!silent) {
        setLoading(false)
      }
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

  useEffect(() => {
    if (!bulkPolling) {
      return
    }
    const interval = window.setInterval(() => {
      void getDashboard()
        .then((data) => setDashboard(data))
        .catch(() => undefined)
    }, 2000)
    const timeout = window.setTimeout(() => setBulkPolling(false), 30000)
    return () => {
      window.clearInterval(interval)
      window.clearTimeout(timeout)
    }
  }, [bulkPolling])

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

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDirection('asc')
    }
  }

  function sortIndicator(key: SortKey): string {
    if (sortKey !== key) {
      return ''
    }
    return sortDirection === 'asc' ? ' ↑' : ' ↓'
  }

  const repositories = useMemo(() => {
    if (!dashboard) {
      return []
    }
    let items: DashboardRepository[]
    if (filter === 'attention') {
      items = dashboard.repositories.filter(needsAttention)
    } else if (filter === 'untracked') {
      items = dashboard.repositories.filter((repository) => !repository.tracked)
    } else if (filter === 'mirror') {
      items = dashboard.repositories.filter(hasMirrorIssue)
    } else {
      items = dashboard.repositories
    }

    const needle = query.trim().toLowerCase()
    if (needle) {
      items = items.filter(
        (repository) =>
          displayName(repository).toLowerCase().includes(needle) ||
          repository.path.toLowerCase().includes(needle),
      )
    }

    const direction = sortDirection === 'asc' ? 1 : -1
    return [...items].sort((left, right) => {
      if (sortKey === 'status') {
        const l = left.status?.state ?? ''
        const r = right.status?.state ?? ''
        return l.localeCompare(r) * direction
      }
      if (sortKey === 'ahead') {
        const l = (left.status?.ahead ?? 0) - (right.status?.ahead ?? 0)
        if (l !== 0) {
          return l * direction
        }
        return ((left.status?.behind ?? 0) - (right.status?.behind ?? 0)) * direction
      }
      return displayName(left).localeCompare(displayName(right)) * direction
    })
  }, [dashboard, filter, query, sortKey, sortDirection])

  const selectedSet = useMemo(() => new Set(selectedRepoIds), [selectedRepoIds])
  const selectedVisible = useMemo(
    () => repositories.filter((repository) => selectedSet.has(repository.id)),
    [repositories, selectedSet],
  )
  const allSelected = repositories.length > 0 && selectedVisible.length === repositories.length

  const summary = dashboard?.summary

  function handleSelectAll() {
    if (allSelected) {
      setSelected(selectedRepoIds.filter((id) => !repositories.some((repo) => repo.id === id)))
    } else {
      setSelected([...new Set([...selectedRepoIds, ...repositories.map((repo) => repo.id)])])
    }
  }

  function startResize(column: ColumnKey, event: ReactMouseEvent) {
    event.preventDefault()
    event.stopPropagation()
    const startX = event.clientX
    const startWidth = columnWidths[column]
    const onMove = (moveEvent: MouseEvent) => {
      setColumnWidth(column, startWidth + moveEvent.clientX - startX)
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  async function handleBulk(kind: 'fetch' | 'sync' | 'migrate') {
    const ids = selectedVisible.length > 0 ? selectedVisible.map((repo) => repo.id) : undefined
    setBulkMessage(
      ids
        ? `Задача для ${ids.length} выбранных запущена в фоне…`
        : 'Задача запущена в фоне…',
    )
    try {
      if (kind === 'fetch') {
        await bulkFetchAll(ids)
      } else if (kind === 'sync') {
        await bulkSyncMirrorsAll(ids)
      } else {
        await migrateToGitflic()
        setBulkMessage('Миграция на GitFlic запущена в фоне…')
      }
      setBulkPolling(true)
    } catch {
      setBulkMessage('Не удалось запустить задачу.')
    }
  }

  async function handleContextFetch(repository: DashboardRepository) {
    try {
      const entry = await runAction(repository.id, 'fetch')
      setBulkMessage(`Fetch ${displayName(repository)}: ${entry.status}`)
      await loadDashboard(true)
    } catch {
      setBulkMessage(`Fetch ${displayName(repository)}: ошибка`)
    }
  }

  async function handleCopyPath(repository: DashboardRepository) {
    try {
      await navigator.clipboard.writeText(repository.path)
      setBulkMessage(`Путь скопирован: ${repository.path}`)
    } catch {
      setBulkMessage('Не удалось скопировать путь.')
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Дашборд</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Локальное состояние репозиториев и расхождения с remote.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleScan()}
          disabled={scanning}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
        >
          {scanning ? 'Сканирование…' : 'Сканировать'}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/40 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void handleBulk('fetch')}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {selectedVisible.length > 0
              ? `Fetch Selected (${selectedVisible.length})`
              : 'Fetch All'}
          </button>
          <button
            type="button"
            onClick={() => void handleBulk('sync')}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {selectedVisible.length > 0
              ? `Sync Selected (${selectedVisible.length})`
              : 'Sync Mirrors'}
          </button>
          <button
            type="button"
            onClick={() => void handleBulk('migrate')}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Мигрировать на GitFlic
          </button>
          {selectedRepoIds.length > 0 && (
            <button
              type="button"
              onClick={clearSelected}
              className="text-xs font-medium text-slate-500 underline-offset-2 hover:underline dark:text-slate-400"
            >
              Сбросить выбор ({selectedVisible.length})
            </button>
          )}
          <div className="relative">
            <button
              type="button"
              onClick={() => setColumnsOpen((current) => !current)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              Колонки
            </button>
            {columnsOpen && (
              <div className="absolute left-0 top-full z-30 mt-1 w-48 rounded-lg border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-900">
                {COLUMN_LABELS.map((column) => (
                  <label
                    key={column.key}
                    className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    <input
                      type="checkbox"
                      checked={visibleColumns[column.key]}
                      onChange={() => toggleColumn(column.key)}
                    />
                    {column.label}
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Поиск по имени или пути…"
          className="w-full max-w-xs rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        />
      </div>

      {bulkMessage && (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
          {bulkMessage}
          {bulkPolling ? ' Обновление статусов каждые 2 с…' : ''}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
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
        <SummaryCard
          label="Зеркала расходятся"
          value={summary?.mirror_issues ?? 0}
          testId="summary-mirror"
        />
      </div>

      {summary && (
        <Suspense
          fallback={
            <p className="text-sm text-slate-500 dark:text-slate-400">Загрузка графиков…</p>
          }
        >
          <DashboardCharts summary={summary} />
        </Suspense>
      )}

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setFilter(item.id)}
                className={`rounded-full px-3 py-1 text-sm font-medium transition ${
                  filter === item.id
                    ? 'bg-primary text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {repositories.length} репозиториев
            {selectedVisible.length > 0 ? ` · выбрано ${selectedVisible.length}` : ''}
          </span>
        </div>

        {loading ? (
          <p className="px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
            Загрузка…
          </p>
        ) : repositories.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
            Нет репозиториев. Запустите сканирование.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
              <colgroup>
                <col style={{ width: 40 }} />
                <col />
                {visibleColumns.branch && <col style={{ width: columnWidths.branch }} />}
                {visibleColumns.status && <col style={{ width: columnWidths.status }} />}
                {visibleColumns.mirror && <col style={{ width: columnWidths.mirror }} />}
                {visibleColumns.ci && <col style={{ width: columnWidths.ci }} />}
                {visibleColumns.aheadBehind && (
                  <col style={{ width: columnWidths.aheadBehind }} />
                )}
                <col style={{ width: 100 }} />
              </colgroup>
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800/50 dark:text-slate-400">
                <tr>
                  <th className="px-3 py-3">
                    <input
                      type="checkbox"
                      aria-label="Выбрать все"
                      checked={allSelected}
                      ref={(element) => {
                        if (element) {
                          element.indeterminate =
                            selectedVisible.length > 0 && !allSelected
                        }
                      }}
                      onChange={handleSelectAll}
                    />
                  </th>
                  <th className="px-4 py-3 font-medium">
                    <button
                      type="button"
                      onClick={() => toggleSort('name')}
                      className="hover:text-slate-800 dark:hover:text-slate-200"
                    >
                      Репозиторий{sortIndicator('name')}
                    </button>
                  </th>
                  {visibleColumns.branch && (
                    <th className="relative px-4 py-3 font-medium">
                      Ветка
                      <span
                        onMouseDown={(event) => startResize('branch', event)}
                        className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                      />
                    </th>
                  )}
                  {visibleColumns.status && (
                    <th className="relative px-4 py-3 font-medium">
                      <button
                        type="button"
                        onClick={() => toggleSort('status')}
                        className="hover:text-slate-800 dark:hover:text-slate-200"
                      >
                        Статус{sortIndicator('status')}
                      </button>
                      <span
                        onMouseDown={(event) => startResize('status', event)}
                        className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                      />
                    </th>
                  )}
                  {visibleColumns.mirror && (
                    <th className="relative px-4 py-3 font-medium">
                      Зеркало
                      <span
                        onMouseDown={(event) => startResize('mirror', event)}
                        className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                      />
                    </th>
                  )}
                  {visibleColumns.ci && (
                    <th className="relative px-4 py-3 font-medium">
                      CI
                      <span
                        onMouseDown={(event) => startResize('ci', event)}
                        className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                      />
                    </th>
                  )}
                  {visibleColumns.aheadBehind && (
                    <th className="relative px-4 py-3 font-medium">
                      <button
                        type="button"
                        onClick={() => toggleSort('ahead')}
                        className="hover:text-slate-800 dark:hover:text-slate-200"
                      >
                        Ahead / Behind{sortIndicator('ahead')}
                      </button>
                      <span
                        onMouseDown={(event) => startResize('aheadBehind', event)}
                        className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                      />
                    </th>
                  )}
                  <th className="px-4 py-3 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {repositories.map((repository) => (
                  <tr
                    key={repository.id}
                    onClick={() => navigate(`/repo/${repository.id}`)}
                    onContextMenu={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setContextMenu({
                        x: event.clientX,
                        y: event.clientY,
                        repository,
                      })
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        navigate(`/repo/${repository.id}`)
                      }
                    }}
                    tabIndex={0}
                    className="cursor-pointer hover:bg-slate-50 focus:bg-slate-50 focus:outline-none dark:hover:bg-slate-800/60 dark:focus:bg-slate-800/60"
                  >
                    <td
                      className="px-3 py-3"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        aria-label={`Выбрать ${displayName(repository)}`}
                        checked={selectedSet.has(repository.id)}
                        onChange={() => toggleSelected(repository.id)}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/repo/${repository.id}`}
                        className="font-medium text-slate-900 hover:text-primary dark:text-slate-100"
                      >
                        {displayName(repository)}
                      </Link>
                      <p
                        className="max-w-xs truncate font-mono text-xs text-slate-500 dark:text-slate-400"
                        title={repository.path}
                      >
                        {repository.path}
                      </p>
                    </td>
                    {visibleColumns.branch && (
                      <td className="px-4 py-3 font-mono text-slate-700 dark:text-slate-300">
                        {repository.status?.branch ?? '—'}
                      </td>
                    )}
                    {visibleColumns.status && (
                      <td className="px-4 py-3">
                        <StatusBadge
                          state={repository.status?.state}
                          tracked={repository.tracked}
                        />
                      </td>
                    )}
                    {visibleColumns.mirror && (
                      <td className="px-4 py-3">
                        <MirrorBadge status={repository.mirror?.mirror_status} />
                      </td>
                    )}
                    {visibleColumns.ci && (
                      <td className="px-4 py-3">
                        <Link
                          to={`/repo/${repository.id}`}
                          className="font-mono text-xs text-primary hover:underline"
                          title="CI status в деталях репозитория"
                        >
                          CI →
                        </Link>
                      </td>
                    )}
                    {visibleColumns.aheadBehind && (
                      <td className="px-4 py-3 font-mono text-slate-700 dark:text-slate-300">
                        {repository.status
                          ? `↑${repository.status.ahead} ↓${repository.status.behind}`
                          : '—'}
                      </td>
                    )}
                    <td className="px-4 py-3">
                      {repository.tracked ? (
                        <Link
                          to={`/repo/${repository.id}`}
                          className="text-sm font-medium text-primary hover:underline"
                        >
                          Детали
                        </Link>
                      ) : (
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation()
                            void handleTrack(repository.id)
                          }}
                          disabled={busyRepository === repository.id}
                          className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
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

      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onClose={() => setContextMenu(null)}
          items={[
            {
              label: 'Открыть детали',
              onSelect: () => navigate(`/repo/${contextMenu.repository.id}`),
            },
            {
              label: 'Сделать Fetch',
              onSelect: () => void handleContextFetch(contextMenu.repository),
            },
            {
              label: 'Скопировать путь',
              onSelect: () => void handleCopyPath(contextMenu.repository),
            },
          ]}
        />
      )}
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
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p
        className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-100"
        data-testid={testId}
      >
        {value}
      </p>
    </div>
  )
}
