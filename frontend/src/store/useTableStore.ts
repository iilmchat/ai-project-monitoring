import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ColumnKey = 'branch' | 'status' | 'mirror' | 'aheadBehind' | 'ci'

export const DEFAULT_COLUMN_WIDTHS: Record<ColumnKey, number> = {
  branch: 110,
  status: 120,
  mirror: 150,
  aheadBehind: 120,
  ci: 90,
}

interface TableState {
  selectedRepoIds: number[]
  visibleColumns: Record<ColumnKey, boolean>
  columnWidths: Record<ColumnKey, number>
  toggleSelected: (repositoryId: number) => void
  setSelected: (repositoryIds: number[]) => void
  clearSelected: () => void
  toggleColumn: (column: ColumnKey) => void
  setVisibleColumns: (columns: Record<ColumnKey, boolean>) => void
  setColumnWidth: (column: ColumnKey, width: number) => void
}

export const useTableStore = create<TableState>()(
  persist(
    (set) => ({
      selectedRepoIds: [],
      visibleColumns: {
        branch: true,
        status: true,
        mirror: true,
        aheadBehind: true,
        ci: true,
      },
      columnWidths: { ...DEFAULT_COLUMN_WIDTHS },
      toggleSelected: (repositoryId) =>
        set((state) => ({
          selectedRepoIds: state.selectedRepoIds.includes(repositoryId)
            ? state.selectedRepoIds.filter((id) => id !== repositoryId)
            : [...state.selectedRepoIds, repositoryId],
        })),
      setSelected: (repositoryIds) => set({ selectedRepoIds: repositoryIds }),
      clearSelected: () => set({ selectedRepoIds: [] }),
      toggleColumn: (column) =>
        set((state) => ({
          visibleColumns: {
            ...state.visibleColumns,
            [column]: !state.visibleColumns[column],
          },
        })),
      setVisibleColumns: (columns) => set({ visibleColumns: { ...columns } }),
      setColumnWidth: (column, width) =>
        set((state) => ({
          columnWidths: {
            ...state.columnWidths,
            [column]: Math.max(70, Math.round(width)),
          },
        })),
    }),
    {
      name: 'table.state',
      version: 1,
    },
  ),
)
