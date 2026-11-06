import {
  DEFAULT_COLUMN_WIDTHS,
  type ColumnKey,
  type TableExportState,
} from '../store/useTableStore'
import type {
  SavedView,
  SavedViewFilters,
  SavedViewSorting,
} from '../store/useViewsStore'

export const WORKSPACE_VERSION = 1
export const WORKSPACE_APP_VERSION = '0.6.0'
export const WORKSPACE_FILENAME = 'iiruchating_workspace.json'

export const COLUMN_KEYS: ColumnKey[] = [
  'branch',
  'status',
  'mirror',
  'aheadBehind',
  'ci',
]

const SORT_KEYS: SavedViewSorting['key'][] = ['name', 'status', 'ahead']

export interface WorkspaceTable {
  visible_columns: Record<ColumnKey, boolean>
  column_widths: Record<ColumnKey, number>
}

export interface WorkspaceState {
  version: 1
  exported_at: string
  app_version: string
  views: SavedView[]
  table: WorkspaceTable
}

export function buildWorkspace({
  views,
  table,
  exportedAt = new Date(),
}: {
  views: SavedView[]
  table: TableExportState
  exportedAt?: Date
}): WorkspaceState {
  return {
    version: WORKSPACE_VERSION,
    exported_at: exportedAt.toISOString(),
    app_version: WORKSPACE_APP_VERSION,
    views: views.map(cloneView),
    table: {
      visible_columns: { ...table.visibleColumns },
      column_widths: { ...table.columnWidths },
    },
  }
}

/**
 * Validate and normalize an imported workspace. Only UI settings are accepted;
 * unknown fields are ignored and malformed entries are dropped.
 */
export function parseWorkspace(raw: unknown): WorkspaceState {
  if (!isRecord(raw)) {
    throw new Error('workspace must be an object')
  }
  if (raw.version !== WORKSPACE_VERSION) {
    throw new Error('unsupported workspace version')
  }
  if (!Array.isArray(raw.views)) {
    throw new Error('workspace views must be an array')
  }

  const views = raw.views
    .map((value, index) => normalizeView(value, index))
    .filter((view): view is SavedView => view !== null)

  const table = normalizeTable(raw.table)
  return {
    version: WORKSPACE_VERSION,
    exported_at:
      typeof raw.exported_at === 'string' ? raw.exported_at : new Date().toISOString(),
    app_version:
      typeof raw.app_version === 'string'
        ? raw.app_version
        : WORKSPACE_APP_VERSION,
    views,
    table,
  }
}

export function downloadWorkspace(state: WorkspaceState): void {
  const blob = new Blob([JSON.stringify(state, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = WORKSPACE_FILENAME
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function normalizeView(value: unknown, index: number): SavedView | null {
  if (!isRecord(value)) {
    return null
  }
  const name = typeof value.name === 'string' ? value.name.trim() : ''
  if (!name) {
    return null
  }
  return {
    id:
      typeof value.id === 'string' && value.id
        ? value.id
        : `imported-view-${index}`,
    name,
    filters: normalizeFilters(value.filters),
    sorting: normalizeSorting(value.sorting),
    visibleColumns: normalizeColumns(value.visibleColumns),
  }
}

function normalizeFilters(value: unknown): SavedViewFilters {
  if (!isRecord(value)) {
    return { status: [], mirror: [], ci: [], untrackedOnly: false }
  }
  return {
    status: stringList(value.status),
    mirror: stringList(value.mirror),
    ci: stringList(value.ci),
    untrackedOnly: value.untrackedOnly === true,
  }
}

function normalizeSorting(value: unknown): SavedViewSorting {
  if (!isRecord(value)) {
    return { key: 'name', direction: 'asc' }
  }
  const key = SORT_KEYS.includes(value.key as SavedViewSorting['key'])
    ? (value.key as SavedViewSorting['key'])
    : 'name'
  const direction = value.direction === 'desc' ? 'desc' : 'asc'
  return { key, direction }
}

function normalizeColumns(value: unknown): Record<ColumnKey, boolean> {
  const source: Record<string, unknown> = isRecord(value) ? value : {}
  const columns = {} as Record<ColumnKey, boolean>
  for (const key of COLUMN_KEYS) {
    columns[key] = source[key] !== false
  }
  return columns
}

function normalizeTable(value: unknown): WorkspaceTable {
  const source: Record<string, unknown> = isRecord(value) ? value : {}
  const rawColumns: Record<string, unknown> = isRecord(source.visible_columns)
    ? source.visible_columns
    : isRecord(source.visibleColumns)
      ? source.visibleColumns
      : {}
  const rawWidths: Record<string, unknown> = isRecord(source.column_widths)
    ? source.column_widths
    : isRecord(source.columnWidths)
      ? source.columnWidths
      : {}

  const visible = {} as Record<ColumnKey, boolean>
  const widths = {} as Record<ColumnKey, number>
  for (const key of COLUMN_KEYS) {
    visible[key] = rawColumns[key] !== false
    const width = rawWidths[key]
    widths[key] =
      typeof width === 'number' && Number.isFinite(width)
        ? Math.min(600, Math.max(70, Math.round(width)))
        : DEFAULT_COLUMN_WIDTHS[key]
  }
  return { visible_columns: visible, column_widths: widths }
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function cloneView(view: SavedView): SavedView {
  return {
    ...view,
    filters: {
      ...view.filters,
      status: [...view.filters.status],
      mirror: [...view.filters.mirror],
      ci: [...view.filters.ci],
    },
    sorting: { ...view.sorting },
    visibleColumns: { ...view.visibleColumns },
  }
}
