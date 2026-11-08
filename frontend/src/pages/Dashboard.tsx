import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent, MouseEvent as ReactMouseEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import {
  bulkFetchAll,
  bulkSyncMirrorsAll,
  exportRepositories,
  getDashboard,
  getScan,
  migrateToGitflic,
  runAction,
  scan,
  trackRepository,
} from '../api/client'
import type { DashboardRepository, DashboardResponse } from '../api/types'
import ContextMenu from '../components/ContextMenu'
import GlobalDependencies from '../components/GlobalDependencies'
import Heatmap from '../components/Heatmap'
import MirrorBadge from '../components/MirrorBadge'
import StatusBadge from '../components/StatusBadge'
import { ciLabel, mirrorLabel, statusLabel, useI18n } from '../i18n'
import { useTableStore } from '../store/useTableStore'
import type { ColumnKey } from '../store/useTableStore'
import { useViewsStore } from '../store/useViewsStore'
import type { SavedViewFilters } from '../store/useViewsStore'
import { buildDashboardMarkdown } from '../utils/markdown'
import { isStatusStale } from '../utils/stale'

const AiDigest = lazy(() => import('../components/AiDigest'))
const DashboardCharts = lazy(() => import('../components/DashboardCharts'))

type SortKey = 'name' | 'status' | 'ahead'
type SortDirection = 'asc' | 'desc'

const STATUS_OPTIONS = ['current', 'dirty', 'ahead', 'behind', 'diverged', 'no_upstream']
const MIRROR_OPTIONS = [
  'in_sync',
  'missing_on_gitflic',
  'missing_on_github',
  'behind_gitflic',
  'behind_github',
  'diverged',
  'history_rewritten',
  'unavailable',
]
const CI_OPTIONS = ['success', 'failure', 'pending']

const EMPTY_FILTERS: SavedViewFilters = {
  status: [],
  mirror: [],
  ci: [],
  untrackedOnly: false,
}

function displayName(repository: DashboardRepository): string {
  if (repository.alias) {
    return repository.alias
  }
  const normalized = repository.path.replaceAll('\\', '/')
  return normalized.split('/').filter(Boolean).pop() ?? repository.path
}

function parseList(value: string | null): string[] {
  return value ? value.split(',').filter(Boolean) : []
}

function hasActiveFilters(filters: SavedViewFilters): boolean {
  return (
    filters.status.length > 0 ||
    filters.mirror.length > 0 ||
    filters.ci.length > 0 ||
    filters.untrackedOnly
  )
}

interface ContextState {
  x: number
  y: number
  repository: DashboardRepository
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { t } = useI18n()
  const [searchParams, setSearchParams] = useSearchParams()

  const stateLabels = Object.fromEntries(
    STATUS_OPTIONS.map((key) => [key, statusLabel(key, t)]),
  )
  const mirrorLabels = Object.fromEntries(
    MIRROR_OPTIONS.map((key) => [key, mirrorLabel(key, t)]),
  )
  const ciLabels = Object.fromEntries(
    CI_OPTIONS.map((key) => [key, ciLabel(key, t)]),
  )
  const columnLabels: { key: ColumnKey; label: string }[] = [
    { key: 'branch', label: t('dashboard.column.branch') },
    { key: 'status', label: t('dashboard.column.status') },
    { key: 'mirror', label: t('dashboard.column.mirror') },
    { key: 'ci', label: t('dashboard.column.ci') },
    { key: 'aheadBehind', label: t('dashboard.column.aheadBehind') },
  ]

  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null)
  const [filters, setFilters] = useState<SavedViewFilters>(() => ({
    status: parseList(searchParams.get('status')),
    mirror: parseList(searchParams.get('mirror')),
    ci: parseList(searchParams.get('ci')),
    untrackedOnly: searchParams.get('tracked') === 'false',
  }))
  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [sortKey, setSortKey] = useState<SortKey>(() => {
    const value = searchParams.get('sort')
    return value === 'status' || value === 'ahead' ? value : 'name'
  })
  const [sortDirection, setSortDirection] = useState<SortDirection>(() =>
    searchParams.get('dir') === 'desc' ? 'desc' : 'asc',
  )

  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [analyticsOpen, setAnalyticsOpen] = useState(false)
  const [busyRepository, setBusyRepository] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [bulkMessage, setBulkMessage] = useState<string | null>(null)
  const [bulkPolling, setBulkPolling] = useState(false)
  const [columnsOpen, setColumnsOpen] = useState(false)
  const [contextMenu, setContextMenu] = useState<ContextState | null>(null)
  const [viewsOpen, setViewsOpen] = useState(false)
  const [saveViewOpen, setSaveViewOpen] = useState(false)
  const [viewName, setViewName] = useState('')
  const [exportOpen, setExportOpen] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [focusedRepoId, setFocusedRepoId] = useState<number | null>(null)
  const rowRefs = useRef<Record<number, HTMLTableRowElement | null>>({})
  const searchRef = useRef<HTMLInputElement>(null)
  const toastTimer = useRef<number | null>(null)

  const selectedRepoIds = useTableStore((state) => state.selectedRepoIds)
  const visibleColumns = useTableStore((state) => state.visibleColumns)
  const columnWidths = useTableStore((state) => state.columnWidths)
  const toggleSelected = useTableStore((state) => state.toggleSelected)
  const setSelected = useTableStore((state) => state.setSelected)
  const clearSelected = useTableStore((state) => state.clearSelected)
  const toggleColumn = useTableStore((state) => state.toggleColumn)
  const setVisibleColumns = useTableStore((state) => state.setVisibleColumns)
  const setColumnWidth = useTableStore((state) => state.setColumnWidth)

  const savedViews = useViewsStore((state) => state.views)
  const addView = useViewsStore((state) => state.addView)
  const removeView = useViewsStore((state) => state.removeView)

  async function loadDashboard(silent = false) {
    if (!silent) {
      setLoading(true)
    }
    try {
      setDashboard(await getDashboard())
      setError(null)
    } catch {
      setError(t('dashboard.loadError'))
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
          setError(t('dashboard.loadError'))
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

  useEffect(() => {
    return () => {
      if (toastTimer.current !== null) {
        window.clearTimeout(toastTimer.current)
      }
    }
  }, [])

  useEffect(() => {
    const next = new URLSearchParams()
    if (filters.status.length) next.set('status', filters.status.join(','))
    if (filters.mirror.length) next.set('mirror', filters.mirror.join(','))
    if (filters.ci.length) next.set('ci', filters.ci.join(','))
    if (filters.untrackedOnly) next.set('tracked', 'false')
    if (query.trim()) next.set('q', query.trim())
    if (sortKey !== 'name' || sortDirection !== 'asc') {
      next.set('sort', sortKey)
      next.set('dir', sortDirection)
    }
    setSearchParams(next, { replace: true })
  }, [filters, query, sortKey, sortDirection])

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
      setError(t('dashboard.scanError'))
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
      setError(t('dashboard.trackError'))
    } finally {
      setBusyRepository(null)
    }
  }

  function toggleFilter(category: 'status' | 'mirror' | 'ci', value: string) {
    setFilters((current) => {
      const values = current[category]
      return {
        ...current,
        [category]: values.includes(value)
          ? values.filter((item) => item !== value)
          : [...values, value],
      }
    })
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
    let items = dashboard.repositories

    if (filters.status.length) {
      items = items.filter(
        (repository) =>
          repository.status !== null && filters.status.includes(repository.status.state),
      )
    }
    if (filters.mirror.length) {
      items = items.filter(
        (repository) =>
          repository.mirror !== null &&
          filters.mirror.includes(repository.mirror.mirror_status),
      )
    }
    if (filters.ci.length) {
      items = items.filter(
        (repository) =>
          repository.ci !== null &&
          repository.ci !== undefined &&
          filters.ci.includes(repository.ci.aggregate),
      )
    }
    if (filters.untrackedOnly) {
      items = items.filter((repository) => !repository.tracked)
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
  }, [dashboard, filters, query, sortKey, sortDirection])

  const duplicateGroups = useMemo(() => {
    const groups = new Map<string, DashboardRepository[]>()
    for (const repository of dashboard?.repositories ?? []) {
      const key = displayName(repository).toLowerCase()
      const items = groups.get(key) ?? []
      items.push(repository)
      groups.set(key, items)
    }
    return groups
  }, [dashboard])

  const selectedSet = useMemo(() => new Set(selectedRepoIds), [selectedRepoIds])
  const selectedVisible = useMemo(
    () => repositories.filter((repository) => selectedSet.has(repository.id)),
    [repositories, selectedSet],
  )
  const allSelected = repositories.length > 0 && selectedVisible.length === repositories.length

  const summary = dashboard?.summary

  async function handleCopySummary() {
    const markdown = buildDashboardMarkdown({
      summary,
      repositories,
    })
    try {
      await navigator.clipboard.writeText(markdown)
      showToast(t('dashboard.summaryCopied'))
    } catch {
      showToast(t('dashboard.summaryCopyError'))
    }
  }

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
    if (
      kind === 'migrate' &&
      !window.confirm(t('dashboard.migrateConfirm'))
    ) {
      return
    }
    const ids = selectedVisible.length > 0 ? selectedVisible.map((repo) => repo.id) : undefined
    setBulkMessage(
      ids
        ? t('dashboard.bulkSelected', { count: ids.length })
        : t('dashboard.bulkStarted'),
    )
    try {
      if (kind === 'fetch') {
        await bulkFetchAll(ids)
      } else if (kind === 'sync') {
        await bulkSyncMirrorsAll(ids)
      } else {
        const result = await migrateToGitflic()
        const updated = Number(result.updated ?? 0)
        const skipped = Number(result.skipped ?? 0)
        setBulkMessage(
          t('dashboard.migrateResult', { updated, skipped }) +
            (skipped > 0 ? t('dashboard.migrateSkippedReason') : '') +
            '.',
        )
      }
      setBulkPolling(true)
    } catch {
      setBulkMessage(t('dashboard.bulkError'))
    }
  }

  async function handleContextFetch(repository: DashboardRepository) {
    try {
      const entry = await runAction(repository.id, 'fetch')
      setBulkMessage(`Fetch ${displayName(repository)}: ${entry.status}`)
      await loadDashboard(true)
    } catch {
      setBulkMessage(t('dashboard.fetchError', { name: displayName(repository) }))
    }
  }

  async function handleCopyPath(repository: DashboardRepository) {
    try {
      await navigator.clipboard.writeText(repository.path)
      setBulkMessage(t('dashboard.pathCopied', { path: repository.path }))
    } catch {
      setBulkMessage(t('dashboard.pathCopyError'))
    }
  }

  function showToast(message: string) {
    setToast(message)
    if (toastTimer.current !== null) {
      window.clearTimeout(toastTimer.current)
    }
    toastTimer.current = window.setTimeout(() => {
      setToast(null)
      toastTimer.current = null
    }, 2500)
  }

  async function handleExport(format: 'csv' | 'json') {
    setExportOpen(false)
    try {
      const blob = await exportRepositories(format)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `repositories.${format}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setBulkMessage(t('dashboard.exportReady', { format: format.toUpperCase() }))
    } catch {
      setBulkMessage(t('dashboard.exportError'))
    }
  }

  function handleTableKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    const target = event.target as HTMLElement
    if (
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement
    ) {
      return
    }

    const currentIndex = repositories.findIndex(
      (repository) => repository.id === focusedRepoId,
    )

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const delta = event.key === 'ArrowDown' ? 1 : -1
      const nextIndex = Math.min(
        Math.max(currentIndex === -1 ? (delta > 0 ? 0 : repositories.length - 1) : currentIndex + delta, 0),
        repositories.length - 1,
      )
      const next = repositories[nextIndex]
      if (next) {
        setFocusedRepoId(next.id)
        rowRefs.current[next.id]?.focus()
      }
      return
    }

    if (event.key === 'Enter') {
      const current = repositories.find((repository) => repository.id === focusedRepoId)
      if (current) {
        event.preventDefault()
        navigate(`/repo/${current.id}`)
      }
      return
    }

    if (event.key === ' ' || event.code === 'Space') {
      const current = repositories.find((repository) => repository.id === focusedRepoId)
      if (current) {
        event.preventDefault()
        toggleSelected(current.id)
      }
      return
    }

    if (event.key === '/') {
      event.preventDefault()
      searchRef.current?.focus()
      return
    }

    if (event.key === 'Escape') {
      event.preventDefault()
      setFocusedRepoId(null)
      if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur()
      }
    }
  }

  function applyView(viewId: string) {
    const view = savedViews.find((item) => item.id === viewId)
    if (!view) {
      return
    }
    setFilters({ ...view.filters })
    setSortKey(view.sorting.key)
    setSortDirection(view.sorting.direction)
    setVisibleColumns(view.visibleColumns)
    setViewsOpen(false)
  }

  function applySummaryFilter(
    kind: 'total' | 'clean' | 'attention' | 'untracked' | 'mirror',
  ) {
    if (kind === 'total') {
      setFilters({ ...EMPTY_FILTERS })
    } else if (kind === 'clean') {
      setFilters({ ...EMPTY_FILTERS, status: ['current'] })
    } else if (kind === 'attention') {
      setFilters({
        ...EMPTY_FILTERS,
        status: ['dirty', 'ahead', 'behind', 'diverged', 'no_upstream'],
      })
    } else if (kind === 'untracked') {
      setFilters({ ...EMPTY_FILTERS, untrackedOnly: true })
    } else {
      setFilters({
        ...EMPTY_FILTERS,
        mirror: [
          'missing_on_gitflic',
          'missing_on_github',
          'behind_gitflic',
          'behind_github',
          'diverged',
          'history_rewritten',
          'unavailable',
        ],
      })
    }
    document
      .getElementById('repositories-list')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function handleSaveView(event: FormEvent) {
    event.preventDefault()
    const name = viewName.trim()
    if (!name) {
      return
    }
    addView({
      name,
      filters: { ...filters },
      sorting: { key: sortKey, direction: sortDirection },
      visibleColumns: { ...visibleColumns },
    })
    setViewName('')
    setSaveViewOpen(false)
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t('dashboard.title')}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t('dashboard.subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void handleScan()}
            disabled={scanning}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
          >
            {scanning ? t('dashboard.scanning') : t('dashboard.scan')}
          </button>
          <button
            type="button"
            onClick={() => void handleCopySummary()}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {t('dashboard.copySummary')}
          </button>
          <div className="relative">
            <button
              type="button"
              onClick={() => setExportOpen((current) => !current)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {t('dashboard.export')}
            </button>
            {exportOpen && (
              <div className="absolute right-0 top-full z-30 mt-1 w-32 rounded-lg border border-slate-200 bg-white p-1 shadow-xl dark:border-slate-700 dark:bg-slate-900">
                <button
                  type="button"
                  onClick={() => void handleExport('csv')}
                  className="w-full rounded px-2 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  CSV
                </button>
                <button
                  type="button"
                  onClick={() => void handleExport('json')}
                  className="w-full rounded px-2 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  JSON
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/40 dark:text-red-300">
          {error}
        </div>
      )}

      <Suspense
        fallback={
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t('common.loading')}
          </p>
        }
      >
        <AiDigest />
      </Suspense>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void handleBulk('fetch')}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {selectedVisible.length > 0
              ? `${t('dashboard.fetchSelected')} (${selectedVisible.length})`
              : t('dashboard.fetchAll')}
          </button>
          <button
            type="button"
            onClick={() => void handleBulk('sync')}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {selectedVisible.length > 0
              ? `${t('dashboard.syncSelected')} (${selectedVisible.length})`
              : t('dashboard.syncMirrors')}
          </button>
          <button
            type="button"
            onClick={() => void handleBulk('migrate')}
            title={t('dashboard.migrateTitle')}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {t('dashboard.migrateGitflic')}
          </button>
          {selectedRepoIds.length > 0 && (
            <button
              type="button"
              onClick={clearSelected}
              className="text-xs font-medium text-slate-500 underline-offset-2 hover:underline dark:text-slate-400"
            >
              {t('dashboard.resetSelection')} ({selectedVisible.length})
            </button>
          )}
          <div className="relative">
            <button
              type="button"
              onClick={() => setColumnsOpen((current) => !current)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {t('dashboard.columns')}
            </button>
            {columnsOpen && (
              <div className="absolute left-0 top-full z-30 mt-1 w-48 rounded-lg border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-900">
                {columnLabels.map((column) => (
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
          <div className="relative">
            <button
              type="button"
              onClick={() => setViewsOpen((current) => !current)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {t('dashboard.views')}
            </button>
            {viewsOpen && (
              <div className="absolute left-0 top-full z-30 mt-1 w-64 rounded-lg border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-900">
                <button
                  type="button"
                  onClick={() => {
                    setViewsOpen(false)
                    setViewName('')
                    setSaveViewOpen(true)
                  }}
                  className="w-full rounded px-2 py-1.5 text-left text-sm font-medium text-primary hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  {t('dashboard.saveView')}
                </button>
                {savedViews.length === 0 ? (
                  <p className="px-2 py-1.5 text-xs text-slate-500 dark:text-slate-400">
                    {t('dashboard.noViews')}
                  </p>
                ) : (
                  savedViews.map((view) => (
                    <div key={view.id} className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => applyView(view.id)}
                        className="flex-1 truncate rounded px-2 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      >
                        {view.name}
                      </button>
                      <button
                        type="button"
                        aria-label={`${t('dashboard.deleteView')} ${view.name}`}
                        onClick={() => removeView(view.id)}
                        className="rounded px-2 py-1 text-xs text-slate-400 hover:bg-slate-100 hover:text-red-600 dark:hover:bg-slate-800"
                      >
                        ×
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
        <input
          ref={searchRef}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('dashboard.searchPlaceholder')}
          className="w-full max-w-xs rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        />
      </div>

      {bulkMessage && (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
          {bulkMessage}
          {bulkPolling ? t('dashboard.polling') : ''}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setFiltersOpen((current) => !current)}
            aria-expanded={filtersOpen}
            className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500 hover:text-primary dark:text-slate-400"
          >
            <span aria-hidden="true">{filtersOpen ? '▾' : '▸'}</span>
            {t('dashboard.filters')}
            {hasActiveFilters(filters) && (
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold normal-case text-primary">
                {t('dashboard.filtersActive')}
              </span>
            )}
          </button>
          <div className="flex items-center gap-3">
            {hasActiveFilters(filters) && (
              <button
                type="button"
                onClick={() => setFilters({ ...EMPTY_FILTERS })}
                className="text-xs font-medium text-primary hover:underline"
              >
                {t('dashboard.clearAll')}
              </button>
            )}
            <button
              type="button"
              onClick={() => setAnalyticsOpen((current) => !current)}
              aria-expanded={analyticsOpen}
              className="text-xs font-medium text-slate-500 hover:text-primary dark:text-slate-400"
            >
              {analyticsOpen ? t('dashboard.hideAnalytics') : t('dashboard.showAnalytics')}
            </button>
          </div>
        </div>
        {filtersOpen && (
          <div className="mt-3 space-y-2 border-t border-slate-100 pt-3 dark:border-slate-800">
            <FilterRow
              label={t('dashboard.filterStatus')}
              options={STATUS_OPTIONS}
              active={filters.status}
              labels={stateLabels}
              onToggle={(value) => toggleFilter('status', value)}
            />
            <FilterRow
              label={t('dashboard.filterMirror')}
              options={MIRROR_OPTIONS}
              active={filters.mirror}
              labels={mirrorLabels}
              onToggle={(value) => toggleFilter('mirror', value)}
            />
            <FilterRow
              label={t('dashboard.filterCi')}
              options={CI_OPTIONS}
              active={filters.ci}
              labels={ciLabels}
              onToggle={(value) => toggleFilter('ci', value)}
            />
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-20 text-xs font-medium text-slate-500 dark:text-slate-400">
                {t('dashboard.filterOther')}
              </span>
              <FilterChip
                label={t('dashboard.untrackedOnly')}
                active={filters.untrackedOnly}
                onClick={() =>
                  setFilters((current) => ({
                    ...current,
                    untrackedOnly: !current.untrackedOnly,
                  }))
                }
              />
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <SummaryCard
          label={t('dashboard.total')}
          value={summary?.total ?? 0}
          testId="summary-total"
          onClick={() => applySummaryFilter('total')}
          hint={t('dashboard.showAll')}
        />
        <SummaryCard
          label={t('dashboard.clean')}
          value={summary?.clean ?? 0}
          testId="summary-clean"
          onClick={() => applySummaryFilter('clean')}
          hint={t('dashboard.showClean')}
        />
        <SummaryCard
          label={t('dashboard.needsAttention')}
          value={summary?.needs_attention ?? 0}
          testId="summary-attention"
          onClick={() => applySummaryFilter('attention')}
          hint={t('dashboard.showAttention')}
        />
        <SummaryCard
          label={t('dashboard.untrackedOnly')}
          value={summary?.untracked ?? 0}
          testId="summary-untracked"
          onClick={() => applySummaryFilter('untracked')}
          hint={t('dashboard.showUntracked')}
        />
        <SummaryCard
          label={t('dashboard.mirrorIssues')}
          value={summary?.mirror_issues ?? 0}
          testId="summary-mirror"
          onClick={() => applySummaryFilter('mirror')}
          hint={t('dashboard.showMirrorIssues')}
        />
      </div>

      {analyticsOpen && (
        <div className="space-y-6">
          {summary && (
            <Suspense
              fallback={
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('charts.loading')}
                </p>
              }
            >
              <DashboardCharts summary={summary} />
            </Suspense>
          )}

          <Heatmap />

          <GlobalDependencies />
        </div>
      )}

      <div
        id="repositories-list"
        className="scroll-mt-4 rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
          <span className="inline-flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t('common.repositories')}
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {repositories.length}
            </span>
            {selectedVisible.length > 0 && (
              <span className="text-xs text-slate-500 dark:text-slate-400">
                · {t('dashboard.selected', { count: selectedVisible.length })}
              </span>
            )}
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {filters.status.length + filters.mirror.length + filters.ci.length > 0
              ? t('dashboard.activeFilters')
              : t('dashboard.noActiveFilters')}
          </span>
        </div>

        {loading ? (
          <p className="px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
            {t('common.loading')}
          </p>
        ) : repositories.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
            {t('dashboard.noRepositories')}
          </p>
        ) : (
          <div className="overflow-x-auto" onKeyDown={handleTableKeyDown}>
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
                      aria-label={t('dashboard.selectAll')}
                      checked={allSelected}
                      ref={(element) => {
                        if (element) {
                          element.indeterminate = selectedVisible.length > 0 && !allSelected
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
                      {t('dashboard.table.repository')}{sortIndicator('name')}
                    </button>
                  </th>
                  {visibleColumns.branch && (
                    <th className="relative px-4 py-3 font-medium">
                      {t('dashboard.column.branch')}
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
                        {t('dashboard.column.status')}{sortIndicator('status')}
                      </button>
                      <span
                        onMouseDown={(event) => startResize('status', event)}
                        className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                      />
                    </th>
                  )}
                  {visibleColumns.mirror && (
                    <th className="relative px-4 py-3 font-medium">
                      {t('dashboard.column.mirror')}
                      <span
                        onMouseDown={(event) => startResize('mirror', event)}
                        className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                      />
                    </th>
                  )}
                  {visibleColumns.ci && (
                    <th className="relative px-4 py-3 font-medium">
                      {t('dashboard.column.ci')}
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
                        {t('dashboard.column.aheadBehind')}{sortIndicator('ahead')}
                      </button>
                      <span
                        onMouseDown={(event) => startResize('aheadBehind', event)}
                        className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                      />
                    </th>
                  )}
                  <th className="px-4 py-3 font-medium">{t('dashboard.table.actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {repositories.map((repository) => (
                  <tr
                    key={repository.id}
                    ref={(element) => {
                      rowRefs.current[repository.id] = element
                    }}
                    onClick={() => navigate(`/repo/${repository.id}`)}
                    onFocus={() => setFocusedRepoId(repository.id)}
                    onContextMenu={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setContextMenu({
                        x: event.clientX,
                        y: event.clientY,
                        repository,
                      })
                    }}
                    tabIndex={0}
                    aria-selected={focusedRepoId === repository.id}
                    className={`cursor-pointer hover:bg-slate-50 focus:bg-slate-50 focus:outline-none dark:hover:bg-slate-800/60 dark:focus:bg-slate-800/60 ${
                      focusedRepoId === repository.id ? 'ring-2 ring-inset ring-primary' : ''
                    } ${isStatusStale(repository.status) ? 'opacity-60' : ''}`}
                  >
                    <td className="px-3 py-3" onClick={(event) => event.stopPropagation()}>
                      <input
                        type="checkbox"
                        aria-label={t('dashboard.selectRepository', { name: displayName(repository) })}
                        checked={selectedSet.has(repository.id)}
                        onChange={() => toggleSelected(repository.id)}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span className="flex flex-wrap items-center gap-2">
                        <Link
                          to={`/repo/${repository.id}`}
                          className="font-medium text-slate-900 hover:text-primary dark:text-slate-100"
                        >
                          {displayName(repository)}
                        </Link>
                        {(duplicateGroups.get(displayName(repository).toLowerCase())?.length ?? 0) >
                          1 && (
                          <span
                            className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-medium text-sky-800 dark:bg-sky-900/40 dark:text-sky-200"
                            title={`${t('dashboard.duplicateTitle')}\n${(
                              duplicateGroups.get(displayName(repository).toLowerCase()) ?? []
                            )
                              .map((item) => item.path)
                              .join('\n')}`}
                          >
                            {
                              duplicateGroups.get(displayName(repository).toLowerCase())
                                ?.length
                            } {t('dashboard.duplicateBadge')}
                          </span>
                        )}
                      </span>
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
                          stale={isStatusStale(repository.status)}
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
                        <span
                          className="font-mono text-xs text-slate-600 dark:text-slate-300"
                          title={t('dashboard.ciTitle')}
                        >
                          {repository.ci?.aggregate ?? '—'}
                        </span>
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
                          {t('common.details')}
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
                          {busyRepository === repository.id ? '…' : t('dashboard.track')}
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
              label: t('dashboard.openDetails'),
              onSelect: () => navigate(`/repo/${contextMenu.repository.id}`),
            },
            {
              label: t('dashboard.contextFetch'),
              onSelect: () => void handleContextFetch(contextMenu.repository),
            },
            {
              label: t('dashboard.copyPath'),
              onSelect: () => void handleCopyPath(contextMenu.repository),
            },
          ]}
        />
      )}

      {saveViewOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <form
            onSubmit={handleSaveView}
            className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl dark:bg-slate-900"
          >
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              {t('dashboard.saveViewTitle')}
            </h2>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {t('dashboard.saveViewHint')}
            </p>
            <input
              autoFocus
              value={viewName}
              onChange={(event) => setViewName(event.target.value)}
              placeholder={t('dashboard.saveViewPlaceholder')}
              className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setSaveViewOpen(false)}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                disabled={!viewName.trim()}
                className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-container disabled:opacity-50"
              >
                {t('common.save')}
              </button>
            </div>
          </form>
        </div>
      )}

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-50 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-xl dark:bg-slate-100 dark:text-slate-900"
        >
          {toast}
        </div>
      )}
    </section>
  )
}

function FilterChip({
  label,
  title,
  active,
  onClick,
}: {
  label: string
  title?: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={active}
      className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition ${
        active
          ? 'bg-primary text-white'
          : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
      }`}
    >
      {label}
    </button>
  )
}

function FilterRow({
  label,
  options,
  active,
  labels,
  onToggle,
}: {
  label: string
  options: string[]
  active: string[]
  labels?: Record<string, string>
  onToggle: (value: string) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-20 text-xs font-medium text-slate-500 dark:text-slate-400">{label}</span>
      {options.map((option) => (
        <FilterChip
          key={option}
          label={labels?.[option] ?? option}
          title={option}
          active={active.includes(option)}
          onClick={() => onToggle(option)}
        />
      ))}
    </div>
  )
}

function SummaryCard({
  label,
  value,
  testId,
  onClick,
  hint,
}: {
  label: string
  value: number
  testId: string
  onClick?: () => void
  hint?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={hint}
      className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-primary/60 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary dark:border-slate-700 dark:bg-slate-900"
    >
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p
        className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-100"
        data-testid={testId}
      >
        {value}
      </p>
    </button>
  )
}
