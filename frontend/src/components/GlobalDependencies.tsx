import { useEffect, useState } from 'react'

import { getGlobalDependencies } from '../api/client'
import type {
  GlobalDependencyPackage,
  GlobalDependencyReport,
} from '../api/types'

type Ecosystem = 'python' | 'node'
type EcosystemPackage = GlobalDependencyPackage & { ecosystem: Ecosystem }

export default function GlobalDependencies() {
  const [report, setReport] = useState<GlobalDependencyReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load(refresh = false) {
    if (refresh) {
      setRefreshing(true)
    }
    try {
      setReport(await getGlobalDependencies(refresh))
      setError(null)
    } catch {
      setError('Не удалось загрузить глобальные зависимости.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    let active = true
    void getGlobalDependencies()
      .then((data) => {
        if (active) {
          setReport(data)
          setError(null)
        }
      })
      .catch(() => {
        if (active) {
          setError('Не удалось загрузить глобальные зависимости.')
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [])

  const packages: EcosystemPackage[] = report
    ? [
        ...report.ecosystems.python.map((item) => ({
          ...item,
          ecosystem: 'python' as const,
        })),
        ...report.ecosystems.node.map((item) => ({
          ...item,
          ecosystem: 'node' as const,
        })),
      ]
    : []

  return (
    <div
      data-testid="global-dependencies"
      className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Global Dependencies
          </h2>
          {report && (
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {report.summary.packages} пакетов · {report.summary.repositories}{' '}
              репозиториев · {report.summary.unification_candidates} к унификации
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => void load(true)}
          disabled={refreshing || loading}
          className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          {refreshing ? 'Обновление…' : 'Обновить'}
        </button>
      </div>

      <div className="p-4">
        {loading ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Анализ зависимостей всех проектов…
          </p>
        ) : error ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
            {error}
          </p>
        ) : packages.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Нет манифестов зависимостей в отслеживаемых репозиториях.
          </p>
        ) : (
          <>
            {report?.error === 'partial_errors' && (
              <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                Часть репозиториев не удалось проанализировать.
              </p>
            )}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800/50 dark:text-slate-400">
                  <tr>
                    <th className="px-3 py-2 font-medium">Пакет</th>
                    <th className="px-3 py-2 font-medium">Ecosystem</th>
                    <th className="px-3 py-2 font-medium">Latest</th>
                    <th className="px-3 py-2 font-medium">Используемые версии</th>
                    <th className="px-3 py-2 font-medium">Проекты</th>
                    <th className="px-3 py-2 font-medium">Статус</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {packages.map((item) => (
                    <tr
                      key={`${item.ecosystem}-${item.name}`}
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/60"
                    >
                      <td className="px-3 py-2 font-mono text-xs font-medium text-slate-800 dark:text-slate-100">
                        {item.name}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
                        {item.ecosystem}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs text-slate-600 dark:text-slate-300">
                        {item.latest_version ?? '—'}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          {item.distribution.map((distribution) => (
                            <span
                              key={distribution.version}
                              title={distribution.projects.join(', ')}
                              className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                            >
                              {distribution.version}
                              <span className="ml-1 text-slate-400">
                                ×{distribution.projects.length}
                              </span>
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-600 dark:text-slate-300">
                        {item.projects_count}
                      </td>
                      <td className="px-3 py-2">
                        {item.unification_needed ? (
                          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
                            Унифицировать
                          </span>
                        ) : (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200">
                            aligned
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
