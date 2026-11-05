import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { bulkFetchAll, getDashboard, migrateToGitflic, scan } from '../api/client'
import type { DashboardRepository } from '../api/types'

type CommandGroup = 'Репозитории' | 'Страницы' | 'Действия'

interface Command {
  id: string
  title: string
  subtitle?: string
  group: CommandGroup
  run: () => void | Promise<void>
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

function displayName(repository: DashboardRepository): string {
  if (repository.alias) {
    return repository.alias
  }
  const normalized = repository.path.replaceAll('\\', '/')
  return normalized.split('/').filter(Boolean).pop() ?? repository.path
}

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [repositories, setRepositories] = useState<DashboardRepository[]>([])
  const [activeIndex, setActiveIndex] = useState(0)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) {
      return
    }
    setQuery('')
    setActiveIndex(0)
    setLoading(true)
    let active = true
    void getDashboard()
      .then((data) => {
        if (active) setRepositories(data.repositories)
      })
      .catch(() => {
        if (active) setRepositories([])
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    window.setTimeout(() => inputRef.current?.focus(), 0)
    return () => {
      active = false
    }
  }, [open])

  const commands = useMemo<Command[]>(() => {
    const staticCommands: Command[] = [
      {
        id: 'page-dashboard',
        title: 'Дашборд',
        group: 'Страницы',
        run: () => navigate('/'),
      },
      {
        id: 'page-settings',
        title: 'Настройки',
        group: 'Страницы',
        run: () => navigate('/settings'),
      },
      {
        id: 'action-scan',
        title: 'Сканировать репозитории',
        group: 'Действия',
        run: async () => {
          await scan()
          navigate('/')
        },
      },
      {
        id: 'action-fetch-all',
        title: 'Fetch All',
        subtitle: 'git fetch для всех tracked репозиториев',
        group: 'Действия',
        run: async () => {
          await bulkFetchAll()
          navigate('/')
        },
      },
      {
        id: 'action-migrate',
        title: 'Мигрировать на GitFlic',
        subtitle: 'сменить canonical_provider на gitflic',
        group: 'Действия',
        run: async () => {
          await migrateToGitflic()
          navigate('/')
        },
      },
    ]
    const repoCommands: Command[] = repositories.map((repository) => ({
      id: `repo-${repository.id}`,
      title: displayName(repository),
      subtitle: repository.path,
      group: 'Репозитории',
      run: () => navigate(`/repo/${repository.id}`),
    }))
    return [...repoCommands, ...staticCommands]
  }, [navigate, repositories])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) {
      return commands
    }
    return commands.filter(
      (command) =>
        command.title.toLowerCase().includes(needle) ||
        (command.subtitle ?? '').toLowerCase().includes(needle),
    )
  }, [commands, query])

  useEffect(() => {
    setActiveIndex(0)
  }, [query])

  if (!open) {
    return null
  }

  async function runCommand(command: Command) {
    onClose()
    await command.run()
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => Math.min(index + 1, Math.max(filtered.length - 1, 0)))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => Math.max(index - 1, 0))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      const command = filtered[activeIndex]
      if (command) {
        void runCommand(command)
      }
    } else if (event.key === 'Escape') {
      event.preventDefault()
      onClose()
    }
  }

  let lastGroup: CommandGroup | null = null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/50 p-4 pt-24"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command Palette"
        className="w-full max-w-xl overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="border-b border-slate-200 p-3 dark:border-slate-700">
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Поиск репозиториев, страниц и действий…"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
          />
        </div>
        <div className="max-h-80 overflow-y-auto py-1">
          {loading ? (
            <p className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">Загрузка…</p>
          ) : filtered.length === 0 ? (
            <p className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
              Ничего не найдено.
            </p>
          ) : (
            filtered.map((command, index) => {
              const showGroup = command.group !== lastGroup
              lastGroup = command.group
              return (
                <div key={command.id}>
                  {showGroup && (
                    <p className="px-4 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
                      {command.group}
                    </p>
                  )}
                  <button
                    type="button"
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => void runCommand(command)}
                    className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm ${
                      index === activeIndex
                        ? 'bg-primary/10 text-primary dark:bg-primary/20'
                        : 'text-slate-700 dark:text-slate-200'
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{command.title}</span>
                      {command.subtitle && (
                        <span className="block truncate font-mono text-xs text-slate-500 dark:text-slate-400">
                          {command.subtitle}
                        </span>
                      )}
                    </span>
                    <span className="text-xs text-slate-400">↵</span>
                  </button>
                </div>
              )
            })
          )}
        </div>
        <div className="flex items-center justify-between border-t border-slate-200 px-3 py-2 text-[11px] text-slate-400 dark:border-slate-700 dark:text-slate-500">
          <span>↑↓ навигация · Enter выбрать</span>
          <span>Esc закрыть</span>
        </div>
      </div>
    </div>
  )
}
