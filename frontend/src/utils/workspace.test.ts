import { beforeEach, describe, expect, it } from 'vitest'

import {
  DEFAULT_COLUMN_WIDTHS,
  useTableStore,
} from '../store/useTableStore'
import type { TableExportState } from '../store/useTableStore'
import { useViewsStore } from '../store/useViewsStore'
import type { SavedView } from '../store/useViewsStore'
import {
  WORKSPACE_VERSION,
  buildWorkspace,
  parseWorkspace,
} from './workspace'

const view: SavedView = {
  id: 'view-1',
  name: 'Issues',
  filters: {
    status: ['dirty', 'diverged'],
    mirror: ['behind_gitflic'],
    ci: [],
    untrackedOnly: false,
  },
  sorting: { key: 'status', direction: 'desc' },
  visibleColumns: {
    branch: true,
    status: true,
    mirror: false,
    aheadBehind: true,
    ci: false,
  },
}

const table: TableExportState = {
  version: 1,
  visibleColumns: {
    branch: true,
    status: true,
    mirror: false,
    aheadBehind: true,
    ci: false,
  },
  columnWidths: { ...DEFAULT_COLUMN_WIDTHS, branch: 180 },
}

describe('workspace export/import', () => {
  beforeEach(() => {
    useViewsStore.setState({ views: [] })
    useTableStore.setState({
      visibleColumns: {
        branch: true,
        status: true,
        mirror: true,
        aheadBehind: true,
        ci: true,
      },
      columnWidths: { ...DEFAULT_COLUMN_WIDTHS },
    })
  })

  it('round-trips views and table settings', () => {
    const workspace = buildWorkspace({
      views: [view],
      table,
      exportedAt: new Date('2026-11-06T12:00:00Z'),
    })

    expect(workspace.version).toBe(WORKSPACE_VERSION)
    expect(workspace.exported_at).toBe('2026-11-06T12:00:00.000Z')

    const parsed = parseWorkspace(JSON.parse(JSON.stringify(workspace)))

    expect(parsed.views).toHaveLength(1)
    expect(parsed.views[0]).toEqual(view)
    expect(parsed.table.visible_columns).toEqual(table.visibleColumns)
    expect(parsed.table.column_widths.branch).toBe(180)
  })

  it('rejects unsupported versions', () => {
    expect(() => parseWorkspace({ version: 99, views: [], table: {} })).toThrow(
      /version/,
    )
    expect(() => parseWorkspace({ views: [] })).toThrow(/version/)
  })

  it('drops malformed views and normalizes missing fields', () => {
    const parsed = parseWorkspace({
      version: 1,
      views: [{ name: 'Ok' }, { broken: true }, null],
      table: { visible_columns: { ci: false } },
    })

    expect(parsed.views).toHaveLength(1)
    expect(parsed.views[0].name).toBe('Ok')
    expect(parsed.views[0].visibleColumns.branch).toBe(true)
    expect(parsed.views[0].filters.status).toEqual([])
    expect(parsed.table.visible_columns.ci).toBe(false)
    expect(parsed.table.column_widths.branch).toBe(
      DEFAULT_COLUMN_WIDTHS.branch,
    )
  })

  it('applies imported state to both stores', () => {
    const workspace = buildWorkspace({ views: [view], table })

    useViewsStore
      .getState()
      .importState({ version: 1, views: workspace.views })
    useTableStore.getState().importState({
      version: 1,
      visibleColumns: workspace.table.visible_columns,
      columnWidths: workspace.table.column_widths,
    })

    expect(useViewsStore.getState().getExportState().views[0].name).toBe(
      'Issues',
    )
    expect(useTableStore.getState().getExportState().columnWidths.branch).toBe(
      180,
    )
    expect(useTableStore.getState().visibleColumns.ci).toBe(false)
  })

  it('does not copy secrets or scan roots into the payload', () => {
    const serialized = JSON.stringify(buildWorkspace({ views: [view], table }))

    expect(serialized).not.toContain('token')
    expect(serialized).not.toContain('SCAN_ROOTS')
    expect(serialized).not.toContain('scan_roots')
  })
})
