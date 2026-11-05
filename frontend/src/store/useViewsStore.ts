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

interface ViewsState {
  views: SavedView[]
  addView: (view: Omit<SavedView, 'id'>) => void
  removeView: (id: string) => void
}

export const useViewsStore = create<ViewsState>()(
  persist(
    (set) => ({
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
    }),
    {
      name: 'views.state',
      version: 1,
    },
  ),
)
