import { useEffect } from 'react'

export interface ContextMenuItem {
  label: string
  onSelect: () => void
  shortcut?: string
}

interface ContextMenuProps {
  x: number
  y: number
  items: ContextMenuItem[]
  onClose: () => void
}

export default function ContextMenu({ x, y, items, onClose }: ContextMenuProps) {
  useEffect(() => {
    const close = () => onClose()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('click', close)
    document.addEventListener('contextmenu', close)
    document.addEventListener('keydown', onKeyDown)
    window.addEventListener('blur', close)
    return () => {
      document.removeEventListener('click', close)
      document.removeEventListener('contextmenu', close)
      document.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('blur', close)
    }
  }, [onClose])

  return (
    <div
      role="menu"
      style={{ left: x, top: y }}
      className="fixed z-50 min-w-52 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-xl dark:border-slate-700 dark:bg-slate-900"
      onClick={(event) => event.stopPropagation()}
    >
      {items.map((item) => (
        <button
          key={item.label}
          type="button"
          role="menuitem"
          onClick={() => {
            item.onSelect()
            onClose()
          }}
          className="flex w-full items-center justify-between gap-4 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          <span>{item.label}</span>
          {item.shortcut && (
            <span className="text-xs text-slate-400 dark:text-slate-500">{item.shortcut}</span>
          )}
        </button>
      ))}
    </div>
  )
}
