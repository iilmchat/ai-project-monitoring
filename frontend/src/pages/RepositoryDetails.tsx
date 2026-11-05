import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  getLog,
  getRecommendations,
  getRepositories,
  getStatus,
  refreshRepository,
} from '../api/client'
import type {
  CommitInfo,
  Recommendation,
  Repository,
  RepositoryStatus,
} from '../api/types'
import StatusBadge from '../components/StatusBadge'

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return '—'
  }
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('ru-RU')
}

export default function RepositoryDetails() {
  const { id } = useParams<{ id: string }>()
  const repositoryId = Number(id)
  const invalidId = Number.isNaN(repositoryId)

  const [repository, setRepository] = useState<Repository | null>(null)
  const [status, setStatus] = useState<RepositoryStatus | null>(null)
  const [commits, setCommits] = useState<CommitInfo[]>([])
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null)
  const [loading, setLoading] = useState(!invalidId)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (invalidId) {
      return
    }
    let active = true
    void (async () => {
      try {
        const [list, currentStatus, log, tips] = await Promise.all([
          getRepositories(0, 500),
          getStatus(repositoryId),
          getLog(repositoryId, 10),
          getRecommendations(repositoryId),
        ])
        if (!active) {
          return
        }
        setRepository(list.items.find((item) => item.id === repositoryId) ?? null)
        setStatus(currentStatus)
        setCommits(log)
        setRecommendations(tips)
        setError(null)
      } catch {
        if (active) {
          setError('Не удалось загрузить детали репозитория.')
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
  }, [invalidId, repositoryId])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      const updated = await refreshRepository(repositoryId, true)
      setStatus(updated)
      setCommits(await getLog(repositoryId, 10))
      setRecommendations(await getRecommendations(repositoryId))
      setError(null)
    } catch {
      setError('Не удалось обновить статус репозитория.')
    } finally {
      setRefreshing(false)
    }
  }

  async function handleCopy(command: string) {
    try {
      await navigator.clipboard.writeText(command)
      setCopiedCommand(command)
      window.setTimeout(
        () => setCopiedCommand((current) => (current === command ? null : current)),
        2000,
      )
    } catch {
      setError('Не удалось скопировать команду в буфер обмена.')
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/" className="text-sm font-medium text-primary hover:underline">
            ← Назад на дашборд
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            {repository?.alias ?? repository?.path ?? `Репозиторий #${id}`}
          </h1>
        </div>
        <button
          type="button"
          onClick={() => void handleRefresh()}
          disabled={refreshing}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
        >
          {refreshing ? 'Обновление…' : 'Обновить'}
        </button>
      </div>

      {(error ?? (invalidId ? 'Некорректный идентификатор репозитория.' : null)) && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error ?? 'Некорректный идентификатор репозитория.'}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-slate-500">Загрузка…</p>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                Репозиторий
              </h2>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Путь</dt>
                  <dd className="truncate text-right font-medium" title={repository?.path}>
                    {repository?.path ?? '—'}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Отслеживается</dt>
                  <dd className="font-medium">{repository?.tracked ? 'да' : 'нет'}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Ветка</dt>
                  <dd className="font-medium">{status?.branch ?? '—'}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Upstream</dt>
                  <dd className="font-medium">{status?.upstream ?? '—'}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Последний коммит</dt>
                  <dd className="max-w-[60%] truncate text-right font-medium" title={status?.head_subject ?? ''}>
                    {status?.head_subject ?? '—'}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Проверено</dt>
                  <dd className="font-medium">{formatDate(status?.checked_at)}</dd>
                </div>
              </dl>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                Статус
              </h2>
              <div className="mt-3 flex items-center gap-3">
                <StatusBadge state={status?.state} tracked={repository?.tracked ?? false} />
                <span className="text-sm text-slate-500">
                  ahead {status?.ahead ?? 0} / behind {status?.behind ?? 0}
                </span>
              </div>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Изменено</dt>
                  <dd className="font-medium">{status?.dirty.modified ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">В индексе</dt>
                  <dd className="font-medium">{status?.dirty.staged ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Untracked</dt>
                  <dd className="font-medium">{status?.dirty.untracked ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500">Remote</dt>
                  <dd className="font-medium">{status?.remote_status ?? '—'}</dd>
                </div>
                {status?.error && (
                  <div className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
                    {status.error}
                  </div>
                )}
              </dl>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Рекомендации
            </h2>
            {recommendations.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500">Рекомендаций нет.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {recommendations.map((item) => (
                  <li
                    key={`${item.action}-${item.command}`}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-800">{item.reason}</p>
                      <code className="mt-1 block break-all rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700">
                        {item.command}
                      </code>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleCopy(item.command)}
                      className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100"
                    >
                      {copiedCommand === item.command ? 'Скопировано' : 'Копировать'}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Последние коммиты
            </h2>
            {commits.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500">Коммитов нет.</p>
            ) : (
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">SHA</th>
                    <th className="px-4 py-3 font-medium">Сообщение</th>
                    <th className="px-4 py-3 font-medium">Автор</th>
                    <th className="px-4 py-3 font-medium">Дата</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {commits.map((commit) => (
                    <tr key={commit.sha} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono text-xs text-slate-600">
                        {commit.sha.slice(0, 8)}
                      </td>
                      <td className="px-4 py-3">{commit.subject}</td>
                      <td className="px-4 py-3 text-slate-600">{commit.author}</td>
                      <td className="px-4 py-3 text-slate-600">{formatDate(commit.date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </section>
  )
}
