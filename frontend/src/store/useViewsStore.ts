import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import type { ColumnKey } from './useTableStore'

export interface SavedViewFilters {
  status: string[]
  mirror: string[]
  ci: string[]
  untrackedOnly: boolean
}

export interface SavedViewSorting {
  key: 'name' | 'status' | 'ahead'
  direction: 'asc' | 'desc'
}

export interface SavedView {
  id: string
  name: string
  filters: SavedViewFilters
  sorting: SavedViewSorting
  visibleColumns: Record<ColumnKey, boolean>
}

export interface ViewsExportState {
  version: 1
  views: SavedView[]
}

interface ViewsState {
  views: SavedView[]
  addView: (view: Omit<SavedView, 'id'>) => void
  removeView: (id: string) => void
  getExportState: () => ViewsExportState
  importState: (state: ViewsExportState) => void
}

export const useViewsStore = create<ViewsState>()(
  persist(
    (set, get) => ({
      views: [],
      addView: (view) =>
        set((state) => ({
          views: [
            ...state.views,
            {
              ...view,
              id:
                typeof crypto !== 'undefined' && 'randomUUID' in crypto
                  ? crypto.randomUUID()
                  : `view-${Date.now()}`,
            },
          ],
        })),
      removeView: (id) =>
        set((state) => ({ views: state.views.filter((view) => view.id !== id) })),
      getExportState: () => ({
        version: 1,
        views: get().views.map((view) => ({
          ...view,
          filters: {
            ...view.filters,
            status: [...view.filters.status],
            mirror: [...view.filters.mirror],
            ci: [...view.filters.ci],
          },
          sorting: { ...view.sorting },
          visibleColumns: { ...view.visibleColumns },
        })),
      }),
      importState: (state) =>
        set({
          views: state.views.map((view) => ({
            ...view,
            filters: {
              ...view.filters,
              status: [...view.filters.status],
              mirror: [...view.filters.mirror],
              ci: [...view.filters.ci],
            },
            sorting: { ...view.sorting },
            visibleColumns: { ...view.visibleColumns },
          })),
        }),
    }),
    {
      name: 'views.state',
      version: 1,
    },
  ),
)
