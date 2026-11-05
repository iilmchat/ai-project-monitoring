import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  getActions,
  getCiStatus,
  getLog,
  getMirror,
  getRecommendations,
  getRepositories,
  getStatus,
  refreshMirror,
  refreshRepository,
  runAction,
  runMirrorAction,
  updateMirrorPolicy,
} from '../api/client'
import type {
  ActionLog,
  CIStatus,
  CommitInfo,
  MirrorProviderStatus,
  MirrorStatus,
  Recommendation,
  Repository,
  RepositoryStatus,
} from '../api/types'
import MirrorBadge from '../components/MirrorBadge'
import StatusBadge from '../components/StatusBadge'

const EXECUTABLE_ACTIONS: Record<string, string> = {
  stash: 'stash',
  push: 'push',
  pull: 'pull',
  'pull-rebase': 'pull',
}

interface ActionPrompt {
  kind: 'local' | 'mirror'
  action: string
  reason: string
  command: string
}

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
  const [mirror, setMirror] = useState<MirrorStatus | null>(null)
  const [ciStatus, setCiStatus] = useState<CIStatus | null>(null)
  const [mirrorRefreshing, setMirrorRefreshing] = useState(false)
  const [policyOpen, setPolicyOpen] = useState(false)
  const [policyCanonical, setPolicyCanonical] = useState<'github' | 'gitflic' | 'both'>(
    'github',
  )
  const [policyExpected, setPolicyExpected] = useState(true)
  const [policyGithubName, setPolicyGithubName] = useState('')
  const [policyGitflicName, setPolicyGitflicName] = useState('')
  const [history, setHistory] = useState<ActionLog[]>([])
  const [actionPrompt, setActionPrompt] = useState<ActionPrompt | null>(null)
  const [actionConfirmed, setActionConfirmed] = useState(false)
  const [actionRunning, setActionRunning] = useState(false)
  const [actionResult, setActionResult] = useState<string | null>(null)
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
        const [list, currentStatus, log, tips, mirrorStatus, actionHistory, ci] =
          await Promise.all([
            getRepositories(0, 500),
            getStatus(repositoryId),
            getLog(repositoryId, 10),
            getRecommendations(repositoryId),
            getMirror(repositoryId),
            getActions(repositoryId),
            getCiStatus(repositoryId),
          ])
        if (!active) {
          return
        }
        const found = list.items.find((item) => item.id === repositoryId) ?? null
        setRepository(found)
        setStatus(currentStatus)
        setCommits(log)
        setRecommendations(tips)
        setMirror(mirrorStatus)
        setHistory(actionHistory)
        setCiStatus(ci)
        if (found) {
          setPolicyCanonical(
            found.canonical_provider === 'gitflic' ? 'gitflic' : 'github',
          )
          setPolicyExpected(found.mirror_expected)
          setPolicyGithubName(found.github_full_name ?? '')
          setPolicyGitflicName(found.gitflic_full_name ?? '')
        }
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

  async function handleMirrorRefresh() {
    setMirrorRefreshing(true)
    try {
      setMirror(await refreshMirror(repositoryId))
      setError(null)
    } catch {
      setError('Не удалось обновить статус зеркала.')
    } finally {
      setMirrorRefreshing(false)
    }
  }

  function openPolicy() {
    setPolicyCanonical(repository?.canonical_provider === 'gitflic' ? 'gitflic' : 'github')
    setPolicyExpected(repository?.mirror_expected ?? true)
    setPolicyGithubName(repository?.github_full_name ?? '')
    setPolicyGitflicName(repository?.gitflic_full_name ?? '')
    setPolicyOpen(true)
  }

  async function handleSavePolicy(event: FormEvent) {
    event.preventDefault()
    try {
      await updateMirrorPolicy(repositoryId, {
        canonical_provider: policyCanonical,
        mirror_expected: policyExpected,
        github_full_name: policyGithubName,
        gitflic_full_name: policyGitflicName,
      })
      const [updatedMirror, list] = await Promise.all([
        getMirror(repositoryId),
        getRepositories(0, 500),
      ])
      setMirror(updatedMirror)
      setRepository(list.items.find((item) => item.id === repositoryId) ?? null)
      setPolicyOpen(false)
      setError(null)
    } catch {
      setError('Не удалось сохранить политику зеркала.')
    }
  }

  function openAction(prompt: ActionPrompt) {
    setActionPrompt(prompt)
    setActionConfirmed(false)
    setActionResult(null)
  }

  async function handleExecuteAction() {
    if (!actionPrompt) {
      return
    }
    setActionRunning(true)
    try {
      let entry: ActionLog
      if (actionPrompt.kind === 'mirror') {
        entry = await runMirrorAction(repositoryId, actionPrompt.action)
      } else {
        const backendAction =
          EXECUTABLE_ACTIONS[actionPrompt.action] ?? actionPrompt.action
        entry = await runAction(repositoryId, backendAction)
      }
      setActionResult(
        entry.status === 'success'
          ? `Выполнено: ${entry.command}`
          : `Ошибка ${entry.exit_code ?? ''}: ${entry.output ?? entry.command}`,
      )
      setActionPrompt(null)
      setActionConfirmed(false)

      const [updatedStatus, log, tips, mirrorStatus, actionHistory, ci] =
        await Promise.all([
          refreshRepository(repositoryId, false),
          getLog(repositoryId, 10),
          getRecommendations(repositoryId),
          getMirror(repositoryId),
          getActions(repositoryId),
          getCiStatus(repositoryId),
        ])
      setStatus(updatedStatus)
      setCommits(log)
      setRecommendations(tips)
      setMirror(mirrorStatus)
      setHistory(actionHistory)
      setCiStatus(ci)
    } catch {
      setActionResult('Не удалось выполнить действие.')
    } finally {
      setActionRunning(false)
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

      {actionResult && (
        <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm text-slate-700 dark:text-slate-300 shadow-sm">
          {actionResult}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">Загрузка…</p>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Репозиторий
              </h2>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Путь</dt>
                  <dd className="truncate text-right font-medium" title={repository?.path}>
                    {repository?.path ?? '—'}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Отслеживается</dt>
                  <dd className="font-medium">{repository?.tracked ? 'да' : 'нет'}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Ветка</dt>
                  <dd className="font-medium">{status?.branch ?? '—'}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Upstream</dt>
                  <dd className="font-medium">{status?.upstream ?? '—'}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Последний коммит</dt>
                  <dd className="max-w-[60%] truncate text-right font-medium" title={status?.head_subject ?? ''}>
                    {status?.head_subject ?? '—'}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Проверено</dt>
                  <dd className="font-medium">{formatDate(status?.checked_at)}</dd>
                </div>
              </dl>
            </div>

            <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Статус
              </h2>
              <div className="mt-3 flex items-center gap-3">
                <StatusBadge state={status?.state} tracked={repository?.tracked ?? false} />
                <span className="text-sm text-slate-500 dark:text-slate-400">
                  ahead {status?.ahead ?? 0} / behind {status?.behind ?? 0}
                </span>
              </div>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Изменено</dt>
                  <dd className="font-medium">{status?.dirty.modified ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">В индексе</dt>
                  <dd className="font-medium">{status?.dirty.staged ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Untracked</dt>
                  <dd className="font-medium">{status?.dirty.untracked ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Remote</dt>
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

          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                CI Status
              </h2>
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${ciBadgeStyle(
                  ciStatus?.aggregate,
                )}`}
              >
                {ciStatus?.aggregate ?? 'unknown'}
              </span>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {[ciStatus?.github, ciStatus?.gitflic].map((provider, index) => (
                <div
                  key={provider?.provider ?? index}
                  className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 p-3 text-sm"
                >
                  <p className="font-semibold text-slate-700 dark:text-slate-300">
                    {provider?.provider ?? (index === 0 ? 'GitHub' : 'GitFlic')}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    status: {provider?.status ?? '—'}
                    {provider?.conclusion ? ` · ${provider.conclusion}` : ''}
                  </p>
                  {provider?.url && (
                    <a
                      href={provider.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 inline-block text-xs font-medium text-primary hover:underline"
                    >
                      Открыть CI →
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-700 px-4 py-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Зеркало GitHub ↔ GitFlic
              </h2>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void handleMirrorRefresh()}
                  disabled={mirrorRefreshing}
                  className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-60"
                >
                  {mirrorRefreshing ? 'Обновление…' : 'Обновить зеркало'}
                </button>
                <button
                  type="button"
                  onClick={openPolicy}
                  className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Настроить
                </button>
              </div>
            </div>
            <div className="grid gap-4 p-4 md:grid-cols-2">
              <ProviderSummary
                name="GitHub"
                info={mirror?.github ?? null}
                fullName={repository?.github_full_name ?? null}
              />
              <ProviderSummary
                name="GitFlic"
                info={mirror?.gitflic ?? null}
                fullName={repository?.gitflic_full_name ?? null}
              />
            </div>
            <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 dark:border-slate-700 px-4 py-3">
              <MirrorBadge status={mirror?.mirror_status} />
              <span className="text-xs text-slate-500 dark:text-slate-400">
                canonical: {mirror?.canonical_provider ?? repository?.canonical_provider ?? '—'}
                {' · '}mirror expected:{' '}
                {(mirror?.mirror_expected ?? repository?.mirror_expected) ? 'да' : 'нет'}
              </span>
            </div>
            {mirror && mirror.recommendations.length > 0 && (
              <ul className="divide-y divide-slate-100 border-t border-slate-200 dark:border-slate-700">
                {mirror.recommendations.map((item) => (
                  <li
                    key={`${item.action}-${item.command}`}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{item.reason}</p>
                      <code className="mt-1 block break-all rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700 dark:text-slate-300">
                        {item.command}
                      </code>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleCopy(item.command)}
                      className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      {copiedCommand === item.command ? 'Скопировано' : 'Копировать'}
                    </button>
                    {item.action === 'push-mirror' && (
                      <button
                        type="button"
                        onClick={() =>
                          openAction({
                            kind: 'mirror',
                            action: 'push-mirror',
                            reason: item.reason,
                            command: item.command,
                          })
                        }
                        className="rounded-md bg-primary px-3 py-1 text-sm font-medium text-white hover:bg-primary-container"
                      >
                        Выполнить
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm">
            <h2 className="border-b border-slate-200 dark:border-slate-700 px-4 py-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Рекомендации
            </h2>
            {recommendations.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500 dark:text-slate-400">Рекомендаций нет.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {recommendations.map((item) => (
                  <li
                    key={`${item.action}-${item.command}`}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{item.reason}</p>
                      <code className="mt-1 block break-all rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700 dark:text-slate-300">
                        {item.command}
                      </code>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleCopy(item.command)}
                      className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      {copiedCommand === item.command ? 'Скопировано' : 'Копировать'}
                    </button>
                    {EXECUTABLE_ACTIONS[item.action] && (
                      <button
                        type="button"
                        onClick={() =>
                          openAction({
                            kind: 'local',
                            action: item.action,
                            reason: item.reason,
                            command: item.command,
                          })
                        }
                        className="rounded-md bg-primary px-3 py-1 text-sm font-medium text-white hover:bg-primary-container"
                      >
                        Выполнить
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm">
            <h2 className="border-b border-slate-200 dark:border-slate-700 px-4 py-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Последние коммиты
            </h2>
            {commits.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500 dark:text-slate-400">Коммитов нет.</p>
            ) : (
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 dark:bg-slate-800/50 text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-3 font-medium">SHA</th>
                    <th className="px-4 py-3 font-medium">Сообщение</th>
                    <th className="px-4 py-3 font-medium">Автор</th>
                    <th className="px-4 py-3 font-medium">Дата</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {commits.map((commit) => (
                    <tr key={commit.sha} className="hover:bg-slate-50 dark:hover:bg-slate-800/60">
                      <td className="px-4 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">
                        {commit.sha.slice(0, 8)}
                      </td>
                      <td className="px-4 py-3">{commit.subject}</td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{commit.author}</td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{formatDate(commit.date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm">
            <h2 className="border-b border-slate-200 dark:border-slate-700 px-4 py-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              История действий
            </h2>
            {history.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500 dark:text-slate-400">Действий пока не было.</p>
            ) : (
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 dark:bg-slate-800/50 text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-3 font-medium">Дата</th>
                    <th className="px-4 py-3 font-medium">Действие</th>
                    <th className="px-4 py-3 font-medium">Статус</th>
                    <th className="px-4 py-3 font-medium">Команда</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {history.map((entry) => (
                    <tr key={entry.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/60">
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                        {formatDate(entry.created_at)}
                      </td>
                      <td className="px-4 py-3 font-medium">{entry.action}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            entry.status === 'success'
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {entry.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">
                        {entry.command}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {policyOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
              <form
                onSubmit={(event) => void handleSavePolicy(event)}
                className="w-full max-w-md rounded-xl bg-white dark:bg-slate-900 p-6 shadow-xl"
              >
                <h2 className="text-lg font-semibold">Политика зеркала</h2>
                <label className="mt-4 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Канонический провайдер
                  <select
                    value={policyCanonical}
                    onChange={(event) =>
                      setPolicyCanonical(
                        event.target.value as 'github' | 'gitflic' | 'both',
                      )
                    }
                    className="mt-1 block w-full rounded-md border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
                  >
                    <option value="github">GitHub</option>
                    <option value="gitflic">GitFlic</option>
                    <option value="both">Both</option>
                  </select>
                </label>
                <label className="mt-3 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  GitHub full name (owner/repo)
                  <input
                    value={policyGithubName}
                    onChange={(event) => setPolicyGithubName(event.target.value)}
                    placeholder="owner/repo"
                    className="mt-1 block w-full rounded-md border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
                  />
                </label>
                <label className="mt-3 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  GitFlic full name (owner/repo)
                  <input
                    value={policyGitflicName}
                    onChange={(event) => setPolicyGitflicName(event.target.value)}
                    placeholder="owner/repo"
                    className="mt-1 block w-full rounded-md border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
                  />
                </label>
                <label className="mt-3 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={policyExpected}
                    onChange={(event) => setPolicyExpected(event.target.checked)}
                  />
                  Ожидать зеркало (mirror_expected)
                </label>
                <div className="mt-6 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setPolicyOpen(false)}
                    className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1.5 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    Отмена
                  </button>
                  <button
                    type="submit"
                    className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-container"
                  >
                    Сохранить
                  </button>
                </div>
              </form>
            </div>
          )}

          {actionPrompt && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
              <div className="w-full max-w-md rounded-xl bg-white dark:bg-slate-900 p-6 shadow-xl">
                <h2 className="text-lg font-semibold">Подтверждение действия</h2>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{actionPrompt.reason}</p>
                <code className="mt-3 block break-all rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700 dark:text-slate-300">
                  {actionPrompt.command}
                </code>
                <label className="mt-4 flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={actionConfirmed}
                    onChange={(event) => setActionConfirmed(event.target.checked)}
                    className="mt-1"
                  />
                  Я понимаю, что действие изменит репозиторий (pull/push/stash).
                </label>
                <div className="mt-6 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setActionPrompt(null)
                      setActionConfirmed(false)
                    }}
                    className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1.5 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    Отмена
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleExecuteAction()}
                    disabled={!actionConfirmed || actionRunning}
                    className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {actionRunning ? 'Выполнение…' : 'Выполнить'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  )
}

function ciBadgeStyle(aggregate: string | null | undefined): string {
  switch (aggregate) {
    case 'success':
      return 'bg-emerald-100 text-emerald-800 ring-emerald-200'
    case 'failure':
      return 'bg-red-100 text-red-800 ring-red-200'
    case 'cancelled':
      return 'bg-slate-200 text-slate-700 dark:text-slate-300 ring-slate-300'
    case 'pending':
      return 'bg-amber-100 text-amber-800 ring-amber-200'
    default:
      return 'bg-slate-100 text-slate-600 dark:text-slate-400 ring-slate-200'
  }
}

function ProviderSummary({
  name,
  info,
  fullName,
}: {
  name: string
  info: MirrorProviderStatus | null
  fullName: string | null
}) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 p-3 text-sm">
      <p className="font-semibold text-slate-700 dark:text-slate-300">{name}</p>
      <p className="truncate text-xs text-slate-500 dark:text-slate-400" title={info?.full_name ?? fullName ?? ''}>
        {info?.full_name ?? fullName ?? 'не настроено'}
      </p>
      <p className="mt-2 font-mono text-xs text-slate-700 dark:text-slate-300">
        {info?.head_sha ? info.head_sha.slice(0, 12) : '—'}
      </p>
      <p className="text-xs text-slate-500 dark:text-slate-400">branch: {info?.branch ?? '—'}</p>
      <p className="text-xs text-slate-500 dark:text-slate-400">checked: {formatDate(info?.checked_at)}</p>
    </div>
  )
}
