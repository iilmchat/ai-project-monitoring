import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { getGlobalDependencies, getRepositories } from '../api/client'
import type {
  GlobalDependencyPackage,
  GlobalDependencyReport,
} from '../api/types'
import { useI18n } from '../i18n'

type Ecosystem = 'python' | 'node'
type EcosystemTab = 'all' | Ecosystem
type EcosystemPackage = GlobalDependencyPackage & { ecosystem: Ecosystem }

function repositoryLabel(path: string, alias: string | null): string {
  if (alias) {
    return alias
  }
  const normalized = path.replaceAll('\\', '/')
  return normalized.split('/').filter(Boolean).pop() ?? path
}

export default function GlobalDependencies() {
  const { t } = useI18n()
  const [report, setReport] = useState<GlobalDependencyReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ecosystem, setEcosystem] = useState<EcosystemTab>('all')
  const [repositoryIds, setRepositoryIds] = useState<Record<string, number>>({})

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
          setError(t('global.loadError'))
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

  useEffect(() => {
    let active = true
    void getRepositories(0, 500)
      .then((data) => {
        if (!active) {
          return
        }
        const mapping: Record<string, number> = {}
        for (const repository of data.items) {
          mapping[repositoryLabel(repository.path, repository.alias)] = repository.id
        }
        setRepositoryIds(mapping)
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [])

  const allPackages: EcosystemPackage[] = report
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

  const packages =
    ecosystem === 'all'
      ? allPackages
      : allPackages.filter((item) => item.ecosystem === ecosystem)

  const counts = {
    all: allPackages.length,
    python: allPackages.filter((item) => item.ecosystem === 'python').length,
    node: allPackages.filter((item) => item.ecosystem === 'node').length,
  }

  return (
    <div
      data-testid="global-dependencies"
      className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t('global.title')}
          </h2>
          {report && (
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {t('global.summary', {
                shown: packages.length,
                total: report.summary.packages,
                repositories: report.summary.repositories,
                unification: report.summary.unification_candidates,
              })}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void load(true)}
            disabled={refreshing || loading}
            className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            title={t('global.refreshTitle')}
          >
            {refreshing ? t('common.refreshing') : t('common.refresh')}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 px-4 py-2 dark:border-slate-700">
        {(
          [
            ['all', t('global.tabAll'), counts.all],
            ['python', t('global.tabPython'), counts.python],
            ['node', t('global.tabNode'), counts.node],
          ] as const
        ).map(([value, label, count]) => (
          <button
            key={value}
            type="button"
            onClick={() => setEcosystem(value)}
            aria-pressed={ecosystem === value}
            title={t('global.showTab', { name: label.toLowerCase() })}
            className={`rounded-md px-3 py-1 text-sm font-medium ${
              ecosystem === value
                ? 'bg-primary text-white'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
            }`}
          >
            {label}
            <span className="ml-1.5 text-xs opacity-70">{count}</span>
          </button>
        ))}
      </div>

      <div className="p-4">
        {loading ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t('global.loading')}
          </p>
        ) : error ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
            {error}
          </p>
        ) : packages.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t('global.empty')}
          </p>
        ) : (
          <>
            {report?.error === 'partial_errors' && (
              <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                {t('global.partial')}
              </p>
            )}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800/50 dark:text-slate-400">
                  <tr>
                    <th className="px-3 py-2 font-medium">{t('global.package')}</th>
                    <th className="px-3 py-2 font-medium">{t('global.ecosystem')}</th>
                    <th className="px-3 py-2 font-medium">{t('global.latest')}</th>
                    <th className="px-3 py-2 font-medium">{t('global.versions')}</th>
                    <th className="px-3 py-2 font-medium">{t('global.projects')}</th>
                    <th className="px-3 py-2 font-medium">{t('global.status')}</th>
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
                        <details className="group">
                          <summary
                            className="cursor-pointer list-none rounded-md border border-slate-200 px-2 py-0.5 font-medium text-primary hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-800"
                            title={t('global.showProjects')}
                          >
                            {item.projects_count === 1
                              ? t('global.project', { count: item.projects_count })
                              : t('global.projectsPlural', { count: item.projects_count })}
                          </summary>
                          <ul className="mt-2 space-y-1">
                            {item.distribution.flatMap((distribution) =>
                              distribution.projects.map((project) => {
                                const repositoryId = repositoryIds[project]
                                return (
                                  <li
                                    key={`${distribution.version}-${project}`}
                                    className="flex items-center justify-between gap-2"
                                  >
                                    {repositoryId ? (
                                      <Link
                                        to={`/repo/${repositoryId}`}
                                        className="truncate text-primary hover:underline"
                                        title={t('global.openProject', { name: project })}
                                      >
                                        {project}
                                      </Link>
                                    ) : (
                                      <span className="truncate">{project}</span>
                                    )}
                                    <span className="font-mono text-[10px] text-slate-400">
                                      {distribution.version}
                                    </span>
                                  </li>
                                )
                              }),
                            )}
                          </ul>
                        </details>
                      </td>
                      <td className="px-3 py-2">
                        {item.unification_needed ? (
                          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
                            {t('global.unify')}
                          </span>
                        ) : (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200">
                            {t('global.aligned')}
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
