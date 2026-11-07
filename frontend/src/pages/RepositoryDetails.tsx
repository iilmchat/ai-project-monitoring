import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  getActions,
  getCiStatus,
  getConflicts,
  getDependencies,
  getDockerStatus,
  getInsights,
  getLog,
  getMirror,
  getReadme,
  getRecommendations,
  getRepositories,
  getSecurity,
  getSettings,
  getStatus,
  generateCommitMessage,
  explainCve,
  refreshMirror,
  refreshRepository,
  runAction,
  runMirrorAction,
  updateDependencies,
  updateMirrorPolicy,
} from '../api/client'
import type {
  ActionLog,
  CIStatus,
  CommitInfo,
  ConflictsResponse,
  DependencyEcosystemReport,
  DependencyPackage,
  DependencyReport,
  DockerContainer,
  DockerPort,
  DockerStatus,
  InsightsReport,
  MirrorProviderStatus,
  MirrorStatus,
  ReadmeMetadata,
  Recommendation,
  Repository,
  RepositoryStatus,
  SecretFinding,
  SecurityReport,
  SecurityVulnerability,
} from '../api/types'
import MirrorBadge from '../components/MirrorBadge'
import ReadmeModal from '../components/ReadmeModal'
import StatusBadge from '../components/StatusBadge'
import { type TranslationKey, useI18n } from '../i18n'
import { isStatusStale } from '../utils/stale'

type Translate = ReturnType<typeof useI18n>['t']

const EXECUTABLE_ACTIONS: Record<string, string> = {
  stash: 'stash',
  push: 'push',
  pull: 'pull',
  'pull-rebase': 'pull',
}

const RECOMMENDATION_KEYS: Record<string, TranslationKey> = {
  commit: 'repo.recommendation.commit',
  stash: 'repo.recommendation.stash',
  'pull-rebase': 'repo.recommendation.pull-rebase',
  merge: 'repo.recommendation.merge',
  push: 'repo.recommendation.push',
  pull: 'repo.recommendation.pull',
  'set-upstream': 'repo.recommendation.set-upstream',
  'push-mirror': 'repo.recommendation.push-mirror',
  'create-mirror': 'repo.recommendation.create-mirror',
}

const InsightsSparkline = lazy(() => import('../components/InsightsSparkline'))

interface ActionPrompt {
  kind: 'local' | 'mirror'
  action: string
  reason: string
  command: string
}

function recommendationReason(
  item: Recommendation,
  t: Translate,
): string {
  const key = RECOMMENDATION_KEYS[item.action]
  return key ? t(key) : item.reason
}

function repositoryLabel(repository: Repository): string {
  if (repository.alias) {
    return repository.alias
  }
  const normalized = repository.path.replaceAll('\\', '/')
  return normalized.split('/').filter(Boolean).pop() ?? repository.path
}

export default function RepositoryDetails() {
  const { t, formatDate } = useI18n()
  const { id } = useParams<{ id: string }>()
  const repositoryId = Number(id)
  const invalidId = Number.isNaN(repositoryId)

  const [repository, setRepository] = useState<Repository | null>(null)
  const [relatedRepositories, setRelatedRepositories] = useState<Repository[]>([])
  const [status, setStatus] = useState<RepositoryStatus | null>(null)
  const [commits, setCommits] = useState<CommitInfo[]>([])
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [mirror, setMirror] = useState<MirrorStatus | null>(null)
  const [ciStatus, setCiStatus] = useState<CIStatus | null>(null)
  const [conflicts, setConflicts] = useState<ConflictsResponse | null>(null)
  const [dockerStatus, setDockerStatus] = useState<DockerStatus | null>(null)
  const [dockerRefreshing, setDockerRefreshing] = useState(false)
  const [dependencies, setDependencies] = useState<DependencyReport | null>(null)
  const [dependenciesLoading, setDependenciesLoading] = useState(!invalidId)
  const [dependenciesRefreshing, setDependenciesRefreshing] = useState(false)
  const [dependenciesError, setDependenciesError] = useState<string | null>(null)
  const [dependencyEcosystem, setDependencyEcosystem] = useState<'python' | 'node'>(
    'python',
  )
  const [dependencyUpdateOpen, setDependencyUpdateOpen] = useState(false)
  const [dependencyUpdateRunning, setDependencyUpdateRunning] = useState(false)
  const [dependencyUpdateError, setDependencyUpdateError] = useState<string | null>(
    null,
  )
  const [security, setSecurity] = useState<SecurityReport | null>(null)
  const [securityLoading, setSecurityLoading] = useState(!invalidId)
  const [securityRefreshing, setSecurityRefreshing] = useState(false)
  const [securityError, setSecurityError] = useState<string | null>(null)
  const [insights, setInsights] = useState<InsightsReport | null>(null)
  const [insightsLoading, setInsightsLoading] = useState(!invalidId)
  const [insightsRefreshing, setInsightsRefreshing] = useState(false)
  const [insightsError, setInsightsError] = useState<string | null>(null)
  const [llmEnabled, setLlmEnabled] = useState(false)
  const [readme, setReadme] = useState<ReadmeMetadata | null>(null)
  const [readmeOpen, setReadmeOpen] = useState(false)
  const [commitOpen, setCommitOpen] = useState(false)
  const [commitLoading, setCommitLoading] = useState(false)
  const [commitMessage, setCommitMessage] = useState('')
  const [commitConfirmed, setCommitConfirmed] = useState(false)
  const [commitRunning, setCommitRunning] = useState(false)
  const [commitNotice, setCommitNotice] = useState<string | null>(null)
  const [cveOpen, setCveOpen] = useState(false)
  const [cveLoading, setCveLoading] = useState(false)
  const [cveTitle, setCveTitle] = useState('')
  const [cveText, setCveText] = useState('')
  const [cveError, setCveError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<number | null>(null)
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
        const [
          list,
          currentStatus,
          log,
          tips,
          mirrorStatus,
          actionHistory,
          ci,
          conflictData,
          docker,
        ] = await Promise.all([
          getRepositories(0, 500),
          getStatus(repositoryId),
          getLog(repositoryId, 10),
          getRecommendations(repositoryId),
          getMirror(repositoryId),
          getActions(repositoryId),
          getCiStatus(repositoryId),
          getConflicts(repositoryId),
          getDockerStatus(repositoryId).catch(() => null),
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
        setConflicts(conflictData)
        setDockerStatus(docker)
        if (found) {
          const label = repositoryLabel(found).toLowerCase()
          setRelatedRepositories(
            list.items.filter(
              (item) =>
                item.id !== found.id &&
                repositoryLabel(item).toLowerCase() === label,
            ),
          )
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
          setError(t('repo.errors.loadDetails'))
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

  useEffect(() => {
    if (invalidId) {
      return
    }
    let active = true
    setDependenciesLoading(true)
    void getDependencies(repositoryId, 'all')
      .then((report) => {
        if (active) {
          setDependencies(report)
          setDependenciesError(null)
          const python = report.ecosystems.find((item) => item.ecosystem === 'python')
          const node = report.ecosystems.find((item) => item.ecosystem === 'node')
          if (
            python?.status === 'no_manifest' &&
            node !== undefined &&
            node.status !== 'no_manifest'
          ) {
            setDependencyEcosystem('node')
          }
        }
      })
      .catch(() => {
        if (active) {
          setDependenciesError(t('repo.errors.dependencies'))
        }
      })
      .finally(() => {
        if (active) {
          setDependenciesLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [invalidId, repositoryId])

  useEffect(() => {
    if (invalidId) {
      return
    }
    let active = true
    setSecurityLoading(true)
    void getSecurity(repositoryId)
      .then((report) => {
        if (active) {
          setSecurity(report)
          setSecurityError(null)
        }
      })
      .catch(() => {
        if (active) {
          setSecurityError(t('repo.errors.security'))
        }
      })
      .finally(() => {
        if (active) {
          setSecurityLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [invalidId, repositoryId])

  useEffect(() => {
    if (invalidId) {
      return
    }
    let active = true
    setInsightsLoading(true)
    void getInsights(repositoryId)
      .then((report) => {
        if (active) {
          setInsights(report)
          setInsightsError(null)
        }
      })
      .catch(() => {
        if (active) {
          setInsightsError(t('repo.errors.insights'))
        }
      })
      .finally(() => {
        if (active) {
          setInsightsLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [invalidId, repositoryId])

  useEffect(() => {
    if (invalidId) {
      return
    }
    let active = true
    void getSettings()
      .then((settings) => {
        if (active) {
          setLlmEnabled(settings.llm_enabled)
        }
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [invalidId])

  useEffect(() => {
    if (invalidId) {
      return
    }
    let active = true
    void getReadme(repositoryId)
      .then((metadata) => {
        if (active) {
          setReadme(metadata)
        }
      })
      .catch(() => {
        if (active) {
          setReadme(null)
        }
      })
    return () => {
      active = false
    }
  }, [invalidId, repositoryId])

  useEffect(() => {
    return () => {
      if (toastTimer.current !== null) {
        window.clearTimeout(toastTimer.current)
      }
    }
  }, [])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      const updated = await refreshRepository(repositoryId, true)
      setStatus(updated)
      setCommits(await getLog(repositoryId, 10))
      setRecommendations(await getRecommendations(repositoryId))
      setError(null)
    } catch {
      setError(t('repo.errors.refreshStatus'))
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
      setError(t('repo.errors.copyCommand'))
    }
  }

  async function handleMirrorRefresh() {
    setMirrorRefreshing(true)
    try {
      setMirror(await refreshMirror(repositoryId))
      setError(null)
    } catch {
      setError(t('repo.errors.refreshMirror'))
    } finally {
      setMirrorRefreshing(false)
    }
  }

  async function handleDockerRefresh() {
    setDockerRefreshing(true)
    try {
      setDockerStatus(await getDockerStatus(repositoryId, true))
      setError(null)
    } catch {
      setError(t('repo.errors.refreshDocker'))
    } finally {
      setDockerRefreshing(false)
    }
  }

  async function handleDependenciesRefresh() {
    setDependenciesRefreshing(true)
    try {
      setDependencies(await getDependencies(repositoryId, 'all', true))
      setDependenciesError(null)
    } catch {
      setDependenciesError(t('repo.errors.dependencies'))
    } finally {
      setDependenciesRefreshing(false)
    }
  }

  async function handleDependencyUpdate() {
    setDependencyUpdateRunning(true)
    setDependencyUpdateError(null)
    try {
      await updateDependencies(repositoryId, dependencyEcosystem)
      setDependencyUpdateOpen(false)
      showToast(t('repo.toast.dependenciesUpdated'))
      const [report, updatedStatus] = await Promise.all([
        getDependencies(repositoryId, 'all', true),
        refreshRepository(repositoryId, false),
      ])
      setDependencies(report)
      setStatus(updatedStatus)
    } catch {
      setDependencyUpdateError(t('repo.errors.updateDependencies'))
    } finally {
      setDependencyUpdateRunning(false)
    }
  }

  async function handleSecurityRefresh() {
    setSecurityRefreshing(true)
    try {
      setSecurity(await getSecurity(repositoryId, true))
      setSecurityError(null)
    } catch {
      setSecurityError(t('repo.errors.security'))
    } finally {
      setSecurityRefreshing(false)
    }
  }

  async function handleInsightsRefresh() {
    setInsightsRefreshing(true)
    try {
      setInsights(await getInsights(repositoryId, 30, true))
      setInsightsError(null)
    } catch {
      setInsightsError(t('repo.errors.insights'))
    } finally {
      setInsightsRefreshing(false)
    }
  }

  function showToast(message: string) {
    setToast(message)
    if (toastTimer.current !== null) {
      window.clearTimeout(toastTimer.current)
    }
    toastTimer.current = window.setTimeout(() => {
      setToast(null)
      toastTimer.current = null
    }, 2500)
  }

  async function openCommitModal() {
    setCommitOpen(true)
    setCommitConfirmed(false)
    setCommitMessage('')
    setCommitNotice(null)
    setCommitLoading(true)
    try {
      const suggestion = await generateCommitMessage(repositoryId)
      setCommitMessage(suggestion.message)
      if (suggestion.truncated) {
        setCommitNotice(t('repo.commit.truncated'))
      }
    } catch {
      setCommitOpen(false)
      showToast(t('repo.errors.llmUnavailable'))
    } finally {
      setCommitLoading(false)
    }
  }

  async function handleCopyCommitMessage() {
    try {
      await navigator.clipboard.writeText(commitMessage)
      showToast(t('repo.toast.commitCopied'))
    } catch {
      showToast(t('repo.errors.copyCommitMessage'))
    }
  }

  async function handleCommit() {
    const message = commitMessage.trim()
    if (!message || !commitConfirmed) {
      return
    }
    setCommitRunning(true)
    try {
      await runAction(repositoryId, 'commit', message)
      setCommitOpen(false)
      setCommitConfirmed(false)
      showToast(t('repo.toast.commitCreated'))
      const updated = await refreshRepository(repositoryId, false)
      setStatus(updated)
      const [log, tips] = await Promise.all([
        getLog(repositoryId, 10),
        getRecommendations(repositoryId),
      ])
      setCommits(log)
      setRecommendations(tips)
    } catch {
      showToast(t('repo.errors.commitFailed'))
    } finally {
      setCommitRunning(false)
    }
  }

  async function openCveExplain(item: SecurityVulnerability) {
    const cveId = item.cve_ids[0] ?? item.osv_id
    setCveOpen(true)
    setCveTitle(cveId)
    setCveText('')
    setCveError(null)
    setCveLoading(true)
    try {
      const result = await explainCve(
        repositoryId,
        cveId,
        item.summary ?? `${item.package} ${item.version}`,
      )
      setCveText(result.explanation)
    } catch {
      setCveError(t('repo.errors.llmUnavailable'))
    } finally {
      setCveLoading(false)
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
      setError(t('repo.errors.savePolicy'))
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
          ? t('repo.action.success', { command: entry.command })
          : t('repo.action.failure', {
              code: entry.exit_code ?? '',
              detail: entry.output ?? entry.command,
            }),
      )
      setActionPrompt(null)
      setActionConfirmed(false)

      // Refresh status first: recommendations are derived from the stored
      // status, so fetching them in parallel would race the refresh.
      const updatedStatus = await refreshRepository(repositoryId, false)
      setStatus(updatedStatus)
      const [log, tips, mirrorStatus, actionHistory, ci, conflictData, docker] =
        await Promise.all([
          getLog(repositoryId, 10),
          getRecommendations(repositoryId),
          getMirror(repositoryId),
          getActions(repositoryId),
          getCiStatus(repositoryId),
          getConflicts(repositoryId),
          getDockerStatus(repositoryId).catch(() => null),
        ])
      setCommits(log)
      setRecommendations(tips)
      setMirror(mirrorStatus)
      setHistory(actionHistory)
      setCiStatus(ci)
      setConflicts(conflictData)
      setDockerStatus(docker)
    } catch {
      setActionResult(t('repo.errors.executeAction'))
    } finally {
      setActionRunning(false)
    }
  }

  const selectedDependencies =
    dependencies?.ecosystems.find((item) => item.ecosystem === dependencyEcosystem) ?? null

  const securityVulnerabilities =
    security?.ecosystems.flatMap((item) => item.vulnerabilities) ?? []
  const securitySecrets = security?.secrets.findings ?? []
  const securityHasCritical =
    (security?.summary.critical ?? 0) + (security?.summary.high ?? 0) > 0

  const insightsHotspots = insights?.hotspots ?? []
  const insightsCommits = insights?.summary.commits ?? 0
  const maxHotspotCount = insightsHotspots.reduce(
    (max, item) => Math.max(max, item.count),
    0,
  )

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <Link to="/" className="text-sm font-medium text-primary hover:underline">
            {t('repo.backToDashboard')}
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <h1 className="min-w-0 truncate text-2xl font-semibold tracking-tight">
              {readme?.name ??
                repository?.alias ??
                repository?.path ??
                t('repo.fallbackTitle', { id: id ?? '' })}
            </h1>
            {readme?.version && (
              <span
                className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary dark:bg-primary/20"
                title={t('repo.readmeVersionTitle')}
              >
                {readme.version}
              </span>
            )}
            {readme && (
              <button
                type="button"
                onClick={() => setReadmeOpen(true)}
                className="rounded-md border border-slate-300 px-2.5 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                title={t('repo.openReadme', { path: readme.path })}
              >
                README
              </button>
            )}
          </div>
          {repository?.path && (
            <p className="mt-1 truncate font-mono text-xs text-slate-500 dark:text-slate-400" title={repository.path}>
              {repository.path}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {status !== null &&
            status.dirty.modified + status.dirty.staged > 0 &&
            llmEnabled && (
              <button
                type="button"
                onClick={() => void openCommitModal()}
                className="rounded-lg border border-primary px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10"
              >
                {t('repo.commit.generate')}
              </button>
            )}
          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={refreshing}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
          >
            {refreshing ? t('common.refreshing') : t('common.refresh')}
          </button>
        </div>
      </div>

      {(error ?? (invalidId ? t('repo.errors.invalidId') : null)) && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error ?? t('repo.errors.invalidId')}
        </div>
      )}

      {actionResult && (
        <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm text-slate-700 dark:text-slate-300 shadow-sm">
          {actionResult}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t('common.loading')}
        </p>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t('repo.sections.repository')}
              </h2>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">
                    {t('common.path')}
                  </dt>
                  <dd className="truncate text-right font-medium" title={repository?.path}>
                    {repository?.path ?? '—'}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">
                    {t('repo.fields.tracked')}
                  </dt>
                  <dd className="font-medium">
                    {repository?.tracked ? t('common.yes') : t('common.no')}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">
                    {t('common.branch')}
                  </dt>
                  <dd className="font-medium">{status?.branch ?? '—'}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Upstream</dt>
                  <dd className="font-medium">{status?.upstream ?? '—'}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">
                    {t('repo.fields.lastCommit')}
                  </dt>
                  <dd className="max-w-[60%] truncate text-right font-medium" title={status?.head_subject ?? ''}>
                    {status?.head_subject ?? '—'}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">
                    {t('repo.fields.checked')}
                  </dt>
                  <dd className="font-medium">{formatDate(status?.checked_at)}</dd>
                </div>
              </dl>
            </div>

            <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t('common.status')}
              </h2>
              <div className="mt-3 flex items-center gap-3">
                <StatusBadge
                  state={status?.state}
                  tracked={repository?.tracked ?? false}
                  stale={isStatusStale(status)}
                />
                <span className="text-sm text-slate-500 dark:text-slate-400">
                  ahead {status?.ahead ?? 0} / behind {status?.behind ?? 0}
                </span>
              </div>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">
                    {t('repo.fields.modified')}
                  </dt>
                  <dd className="font-medium">{status?.dirty.modified ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">
                    {t('repo.fields.staged')}
                  </dt>
                  <dd className="font-medium">{status?.dirty.staged ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">Untracked</dt>
                  <dd className="font-medium">{status?.dirty.untracked ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-500 dark:text-slate-400">
                    {t('common.remote')}
                  </dt>
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

          {relatedRepositories.length > 0 && (
            <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 shadow-sm dark:border-sky-800 dark:bg-sky-900/20">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-sky-800 dark:text-sky-200">
                  {t('repo.sections.related')}
                </h2>
                <span
                  className="text-xs text-sky-700 dark:text-sky-300"
                  title={t('repo.related.title')}
                >
                  {t('repo.related.note')}
                </span>
              </div>
              <ul className="mt-2 space-y-1">
                {relatedRepositories.map((item) => (
                  <li key={item.id} className="flex flex-wrap items-center gap-2 text-sm">
                    <Link
                      to={`/repo/${item.id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {repositoryLabel(item)}
                    </Link>
                    <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
                      {item.path}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div
            data-testid="recommendations-block"
            className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t('repo.sections.recommendations')}
              </h2>
              <span
                className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                title={t('repo.recommendations.title')}
              >
                {recommendations.length}
              </span>
            </div>
            {recommendations.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500 dark:text-slate-400">
                {t('repo.recommendations.empty')}
              </p>
            ) : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {recommendations.map((item) => (
                  <li
                    key={`${item.action}-${item.command}`}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                        {recommendationReason(item, t)}
                      </p>
                      <code className="mt-1 block break-all rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                        {item.command}
                      </code>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleCopy(item.command)}
                      className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      {copiedCommand === item.command
                        ? t('common.copied')
                        : t('common.copy')}
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
                        {t('repo.actions.execute')}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {status?.state === 'diverged' && (
            <div className="rounded-xl border border-red-200 bg-white p-5 shadow-sm dark:border-red-800 dark:bg-slate-900">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t('repo.sections.conflicts', {
                  count: conflicts?.files.length ?? 0,
                })}
              </h2>
              {conflicts && conflicts.files.length > 0 ? (
                <ul className="mt-3 space-y-1">
                  {conflicts.files.map((file) => (
                    <li
                      key={file}
                      className="rounded bg-red-50 px-2 py-1 font-mono text-xs text-red-700 dark:bg-red-900/30 dark:text-red-300"
                    >
                      {file}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
                  {t('repo.conflicts.empty')}
                </p>
              )}
            </div>
          )}

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
                      {t('repo.ci.open')}
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div
            data-testid="docker-block"
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-700 px-4 py-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Docker Containers
              </h2>
              <div className="flex items-center gap-2">
                <DockerBadge status={dockerStatus?.status} t={t} />
                <button
                  type="button"
                  onClick={() => void handleDockerRefresh()}
                  disabled={dockerRefreshing}
                  className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-60"
                >
                  {dockerRefreshing ? t('common.refreshing') : t('common.refresh')}
                </button>
              </div>
            </div>
            <div className="p-4">
              {dockerStatus === null ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('repo.docker.error')}
                </p>
              ) : (
                <>
                  {dockerStatus.status === 'unavailable' && (
                    <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                      {dockerStatus.error ?? 'Docker daemon not running'}
                    </p>
                  )}
                  {dockerStatus.status === 'not_found' && (
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      {t('repo.docker.notFound')}
                    </p>
                  )}
                  {dockerStatus.containers.length > 0 && (
                    <ul className="space-y-3">
                      {dockerStatus.containers.map((container) => (
                        <li
                          key={container.id || container.name}
                          className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/50"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p
                                className="truncate font-mono text-sm font-semibold text-slate-800 dark:text-slate-100"
                                title={container.name}
                              >
                                {container.name}
                              </p>
                              <p
                                className="truncate text-xs text-slate-500 dark:text-slate-400"
                                title={container.image}
                              >
                                {container.image || '—'}
                              </p>
                            </div>
                            <span
                              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                                container.state === 'running'
                                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200'
                                  : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
                              }`}
                            >
                              {container.status}
                            </span>
                          </div>
                          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                            compose: {container.compose_project ?? '—'}
                            {container.compose_service
                              ? ` / ${container.compose_service}`
                              : ''}
                          </p>
                          <p className="mt-1 break-all font-mono text-xs text-slate-600 dark:text-slate-300">
                            {formatContainerPorts(container, t)}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
                    {t('repo.fields.checkedWithDate', {
                      date: formatDate(dockerStatus.checked_at),
                    })}
                  </p>
                </>
              )}
            </div>
          </div>

          <div
            data-testid="dependencies-block"
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-700 px-4 py-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t('repo.sections.dependencies')}
              </h2>
              <div className="flex items-center gap-2">
                <DependencyBadge report={selectedDependencies} t={t} />
                <button
                  type="button"
                  onClick={() => {
                    setDependencyUpdateError(null)
                    setDependencyUpdateOpen(true)
                  }}
                  disabled={
                    status?.state === 'dirty' ||
                    selectedDependencies?.status === 'no_manifest' ||
                    selectedDependencies?.status === 'parse_error' ||
                    dependenciesLoading ||
                    dependencyUpdateRunning
                  }
                  title={
                    status?.state === 'dirty'
                      ? t('repo.dependencies.commitFirst')
                      : undefined
                  }
                  className="rounded-md border border-amber-300 px-3 py-1 text-sm font-medium text-amber-800 hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-amber-700 dark:text-amber-200 dark:hover:bg-amber-900/20"
                >
                  {t('repo.dependencies.updatePackages')}
                </button>
                <button
                  type="button"
                  onClick={() => void handleDependenciesRefresh()}
                  disabled={dependenciesRefreshing || dependenciesLoading}
                  className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-60"
                >
                  {dependenciesRefreshing
                    ? t('repo.dependencies.checking')
                    : t('repo.dependencies.checkAll')}
                </button>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 px-4 py-2 dark:border-slate-700">
              <button
                type="button"
                onClick={() => setDependencyEcosystem('python')}
                aria-pressed={dependencyEcosystem === 'python'}
                className={`rounded-md px-3 py-1 text-sm font-medium ${
                  dependencyEcosystem === 'python'
                    ? 'bg-primary text-white'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`}
              >
                Python
              </button>
              <button
                type="button"
                onClick={() => setDependencyEcosystem('node')}
                aria-pressed={dependencyEcosystem === 'node'}
                className={`rounded-md px-3 py-1 text-sm font-medium ${
                  dependencyEcosystem === 'node'
                    ? 'bg-primary text-white'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`}
              >
                Node
              </button>
              <span className="ml-auto text-xs text-slate-500 dark:text-slate-400">
                {t('repo.dependencies.totalOutdated', {
                  count: dependencies?.summary.outdated ?? 0,
                })}
              </span>
            </div>
            <div className="p-4">
              {dependenciesLoading ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('repo.dependencies.loading')}
                </p>
              ) : dependenciesError ? (
                <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
                  {dependenciesError}
                </p>
              ) : selectedDependencies === null ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('repo.dependencies.noData')}
                </p>
              ) : (
                <>
                  {selectedDependencies.status === 'no_manifest' && (
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      {selectedDependencies.manifest === 'package.json'
                        ? t('repo.dependencies.packageJsonMissing')
                        : t('repo.dependencies.requirementsMissing')}
                    </p>
                  )}
                  {selectedDependencies.status === 'parse_error' && (
                    <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
                      {selectedDependencies.error ??
                        t('repo.dependencies.parseError', {
                          manifest:
                            selectedDependencies.manifest ??
                            t('repo.dependencies.manifestFallback'),
                        })}
                    </p>
                  )}
                  {selectedDependencies.status === 'unavailable' && (
                    <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                      {dependencyErrorMessage(selectedDependencies.error, t)}
                    </p>
                  )}
                  {selectedDependencies.status !== 'no_manifest' &&
                    selectedDependencies.status !== 'parse_error' && (
                      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                        <DependencyCounter
                          label={t('repo.dependencies.outdated')}
                          value={selectedDependencies.outdated}
                          tone="amber"
                        />
                        <DependencyCounter
                          label={t('repo.dependencies.upToDate')}
                          value={selectedDependencies.up_to_date}
                          tone="emerald"
                        />
                        <DependencyCounter
                          label={t('repo.dependencies.unknown')}
                          value={selectedDependencies.unknown}
                          tone="slate"
                        />
                        <DependencyCounter
                          label={t('repo.dependencies.ignored')}
                          value={selectedDependencies.ignored}
                          tone="slate"
                        />
                      </div>
                    )}
                  {(selectedDependencies.manifests?.length ?? 0) > 0 && (
                    <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                      {t('repo.dependencies.manifests')}{' '}
                      <span
                        className="font-mono text-slate-600 dark:text-slate-300"
                        title={selectedDependencies.manifests?.join('\n')}
                      >
                        {selectedDependencies.manifests?.join(', ')}
                      </span>
                    </p>
                  )}
                  {selectedDependencies.packages.length > 0 ? (
                    <ul className="mt-3 max-h-80 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200 dark:divide-slate-700 dark:border-slate-700">
                      {selectedDependencies.packages.map((item) => (
                        <DependencyPackageRow
                          key={`${item.name}-${item.manifest_line ?? item.declared}`}
                          item={item}
                          ecosystem={selectedDependencies.ecosystem}
                          t={t}
                        />
                      ))}
                    </ul>
                  ) : (
                    selectedDependencies.status === 'ok' && (
                      <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
                        {t('repo.dependencies.noneDeclared')}
                      </p>
                    )
                  )}
                  <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
                    {t('repo.dependencies.footer', {
                      checked: formatDate(dependencies?.checked_at),
                      source: dependencySourceLabel(
                        selectedDependencies.source,
                        t,
                      ),
                      outdated: dependencies?.summary.outdated ?? 0,
                    })}
                  </p>
                </>
              )}
            </div>
          </div>

          <div
            data-testid="security-block"
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-700 px-4 py-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t('repo.sections.security')}
              </h2>
              <div className="flex items-center gap-2">
                <SecurityBadge
                  report={security}
                  hasCritical={securityHasCritical}
                  secrets={securitySecrets.length}
                  t={t}
                />
                <button
                  type="button"
                  onClick={() => void handleSecurityRefresh()}
                  disabled={securityRefreshing || securityLoading}
                  className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-60"
                >
                  {securityRefreshing
                    ? t('repo.dependencies.checking')
                    : t('repo.security.checkAgain')}
                </button>
              </div>
            </div>
            <div className="space-y-3 p-4">
              {securityLoading ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('repo.security.loading')}
                </p>
              ) : securityError ? (
                <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
                  {securityError}
                </p>
              ) : security === null ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('repo.security.noData')}
                </p>
              ) : (
                <>
                  {security.status === 'unavailable' && (
                    <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                      {security.error === 'rate_limited'
                        ? t('repo.security.rateLimited')
                        : t('repo.security.osvUnavailable')}
                    </p>
                  )}

                  {securitySecrets.length > 0 && (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 dark:border-red-800 dark:bg-red-900/30">
                      <p className="text-sm font-semibold text-red-700 dark:text-red-300">
                        {t('repo.security.secretsFound', {
                          count: securitySecrets.length,
                        })}
                      </p>
                      <ul className="mt-2 space-y-1">
                        {securitySecrets.map((finding) => (
                          <li
                            key={`${finding.file}-${finding.line}-${finding.type}`}
                            className="flex flex-wrap items-center gap-2 text-xs text-red-700 dark:text-red-200"
                          >
                            <span className="font-mono">
                              {finding.file}:{finding.line}
                            </span>
                            <span>{secretTypeLabel(finding.type, t)}</span>
                            <code className="rounded bg-red-100 px-1.5 py-0.5 font-mono dark:bg-red-900/50">
                              {finding.preview}
                            </code>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {securityVulnerabilities.length > 0 ? (
                    <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200 dark:divide-slate-700 dark:border-slate-700">
                      {securityVulnerabilities.map((vulnerability) => (
                        <SecurityVulnerabilityRow
                          key={`${vulnerability.package}-${vulnerability.osv_id}`}
                          item={vulnerability}
                          t={t}
                          onExplain={
                            llmEnabled
                              ? () => void openCveExplain(vulnerability)
                              : undefined
                          }
                        />
                      ))}
                    </ul>
                  ) : security.status === 'ok' ? (
                    <p className="text-sm text-emerald-700 dark:text-emerald-300">
                      {t('repo.security.noVulnerabilities')}
                    </p>
                  ) : (
                    <p className="text-sm text-amber-700 dark:text-amber-300">
                      {t('repo.security.vulnerabilitiesUnavailable')}
                    </p>
                  )}

                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    {t('repo.security.footer', {
                      checked: formatDate(security.checked_at),
                      total: security.summary.total_packages,
                      checkedCount: security.summary.packages_checked,
                      unknown: security.summary.unknown,
                      secrets: security.summary.secrets_found,
                    })}
                  </p>
                </>
              )}
            </div>
          </div>

          <div
            data-testid="hotspots-block"
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-700 px-4 py-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t('repo.sections.hotspots')}
              </h2>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {t('repo.hotspots.window', {
                    days: insights?.window.hotspots_days ?? 90,
                  })}
                </span>
                <button
                  type="button"
                  onClick={() => void handleInsightsRefresh()}
                  disabled={insightsRefreshing || insightsLoading}
                  className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-60"
                >
                  {insightsRefreshing
                    ? t('common.refreshing')
                    : t('common.refresh')}
                </button>
              </div>
            </div>
            <div className="p-4">
              {insightsLoading ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('repo.hotspots.loading')}
                </p>
              ) : insightsError ? (
                <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
                  {insightsError}
                </p>
              ) : insights === null ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('repo.hotspots.noData')}
                </p>
              ) : (
                <>
                  {insightsNotice(insights, t) && (
                    <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                      {insightsNotice(insights, t)}
                    </p>
                  )}
                  {insightsHotspots.length > 0 ? (
                    <ul className="space-y-3">
                      {insightsHotspots.map((item) => (
                        <li
                          key={item.file}
                          className="flex items-center justify-between gap-3"
                        >
                          <div className="min-w-0 flex-1">
                            <p
                              className="truncate font-mono text-xs text-slate-700 dark:text-slate-300"
                              title={item.file}
                            >
                              {item.file}
                            </p>
                            <div className="mt-1 h-1.5 rounded bg-slate-100 dark:bg-slate-800">
                              <div
                                className="h-1.5 rounded bg-primary"
                                style={{
                                  width: `${
                                    maxHotspotCount > 0
                                      ? Math.round((item.count / maxHotspotCount) * 100)
                                      : 0
                                  }%`,
                                }}
                              />
                            </div>
                          </div>
                          <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                            {item.count}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      {t('repo.hotspots.noData')}
                    </p>
                  )}
                  <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
                    {t('repo.hotspots.footer')}
                  </p>
                </>
              )}
            </div>
          </div>

          <div
            data-testid="activity-block"
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-700 px-4 py-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t('repo.sections.activity')}
              </h2>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                {t('repo.activity.commits', { count: insightsCommits })}
              </span>
            </div>
            <div className="p-4">
              {insightsLoading ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('repo.activity.loading')}
                </p>
              ) : insightsError ? (
                <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
                  {insightsError}
                </p>
              ) : insights === null || insightsCommits === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('repo.activity.empty')}
                </p>
              ) : (
                <>
                  <Suspense
                    fallback={
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        {t('repo.activity.chartLoading')}
                      </p>
                    }
                  >
                    <InsightsSparkline data={insights.commit_frequency} />
                  </Suspense>
                  <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
                    {t('repo.activity.dora', {
                      value: insights.summary.per_week.toFixed(2),
                    })}
                  </p>
                </>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-700 px-4 py-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t('repo.sections.mirror')}
              </h2>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void handleMirrorRefresh()}
                  disabled={mirrorRefreshing}
                  className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-60"
                >
                  {mirrorRefreshing
                    ? t('common.refreshing')
                    : t('repo.mirror.refresh')}
                </button>
                <button
                  type="button"
                  onClick={openPolicy}
                  className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  {t('repo.mirror.configure')}
                </button>
              </div>
            </div>
            <div className="grid gap-4 p-4 md:grid-cols-2">
              <ProviderSummary
                name="GitHub"
                info={mirror?.github ?? null}
                fullName={repository?.github_full_name ?? null}
                t={t}
              />
              <ProviderSummary
                name="GitFlic"
                info={mirror?.gitflic ?? null}
                fullName={repository?.gitflic_full_name ?? null}
                t={t}
              />
            </div>
            <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 dark:border-slate-700 px-4 py-3">
              <MirrorBadge status={mirror?.mirror_status} />
              <span className="text-xs text-slate-500 dark:text-slate-400">
                canonical: {mirror?.canonical_provider ?? repository?.canonical_provider ?? '—'}
                {' · '}
                {t('repo.mirror.expected', {
                  value: (mirror?.mirror_expected ?? repository?.mirror_expected)
                    ? t('common.yes')
                    : t('common.no'),
                })}
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
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                        {recommendationReason(item, t)}
                      </p>
                      <code className="mt-1 block break-all rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700 dark:text-slate-300">
                        {item.command}
                      </code>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleCopy(item.command)}
                      className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      {copiedCommand === item.command
                        ? t('common.copied')
                        : t('common.copy')}
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
                        {t('repo.actions.execute')}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm">
            <h2 className="border-b border-slate-200 dark:border-slate-700 px-4 py-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t('repo.sections.commits')}
            </h2>
            {commits.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500 dark:text-slate-400">
                {t('repo.commits.empty')}
              </p>
            ) : (
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 dark:bg-slate-800/50 text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-3 font-medium">SHA</th>
                    <th className="px-4 py-3 font-medium">
                      {t('repo.table.message')}
                    </th>
                    <th className="px-4 py-3 font-medium">
                      {t('repo.table.author')}
                    </th>
                    <th className="px-4 py-3 font-medium">
                      {t('repo.table.date')}
                    </th>
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
              {t('repo.sections.history')}
            </h2>
            {history.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500 dark:text-slate-400">
                {t('repo.history.empty')}
              </p>
            ) : (
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 dark:bg-slate-800/50 text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-3 font-medium">
                      {t('repo.table.date')}
                    </th>
                    <th className="px-4 py-3 font-medium">
                      {t('repo.table.action')}
                    </th>
                    <th className="px-4 py-3 font-medium">
                      {t('common.status')}
                    </th>
                    <th className="px-4 py-3 font-medium">
                      {t('repo.table.command')}
                    </th>
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
                <h2 className="text-lg font-semibold">
                  {t('repo.policy.title')}
                </h2>
                <label className="mt-4 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  {t('repo.policy.canonicalProvider')}
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
                  {t('repo.policy.githubFullName')}
                  <input
                    value={policyGithubName}
                    onChange={(event) => setPolicyGithubName(event.target.value)}
                    placeholder="owner/repo"
                    className="mt-1 block w-full rounded-md border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
                  />
                </label>
                <label className="mt-3 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  {t('repo.policy.gitflicFullName')}
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
                  {t('repo.policy.expectMirror')}
                </label>
                <div className="mt-6 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setPolicyOpen(false)}
                    className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1.5 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    type="submit"
                    className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-container"
                  >
                    {t('common.save')}
                  </button>
                </div>
              </form>
            </div>
          )}

          {actionPrompt && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
              <div className="w-full max-w-md rounded-xl bg-white dark:bg-slate-900 p-6 shadow-xl">
                <h2 className="text-lg font-semibold">
                  {t('repo.action.title')}
                </h2>
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
                  {t('repo.action.confirm')}
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
                    {t('common.cancel')}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleExecuteAction()}
                    disabled={!actionConfirmed || actionRunning}
                    className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {actionRunning
                      ? t('repo.action.running')
                      : t('repo.actions.execute')}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {commitOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="commit-message-title"
            className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl dark:bg-slate-900"
          >
            <h2
              id="commit-message-title"
              className="text-lg font-semibold text-slate-900 dark:text-slate-100"
            >
              {t('repo.commit.generate')}
            </h2>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {t('repo.commit.hint')}
            </p>
            {commitLoading ? (
              <p className="mt-6 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                {t('repo.commit.generating')}
              </p>
            ) : (
              <>
                {commitNotice && (
                  <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                    {commitNotice}
                  </p>
                )}
                <textarea
                  value={commitMessage}
                  onChange={(event) => setCommitMessage(event.target.value)}
                  rows={6}
                  className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
                <label className="mt-3 flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={commitConfirmed}
                    onChange={(event) => setCommitConfirmed(event.target.checked)}
                    className="mt-1"
                  />
                  {t('repo.commit.confirm')}
                </label>
                <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                  {t('repo.commit.stagedHint')}
                </p>
                <div className="mt-5 flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setCommitOpen(false)}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleCopyCommitMessage()}
                    disabled={!commitMessage.trim()}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                  >
                    {t('repo.commit.copy')}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleCommit()}
                    disabled={
                      !commitMessage.trim() || !commitConfirmed || commitRunning
                    }
                    className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {commitRunning ? t('repo.commit.running') : t('repo.commit.submit')}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {dependencyUpdateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="dependency-update-title"
            className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl dark:bg-slate-900"
          >
            <h2
              id="dependency-update-title"
              className="text-lg font-semibold text-slate-900 dark:text-slate-100"
            >
              {t('repo.dependencyUpdate.title')}
            </h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              {t('repo.dependencyUpdate.body', { ecosystem: dependencyEcosystem })}
            </p>
            {dependencyUpdateError && (
              <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
                {dependencyUpdateError}
              </p>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDependencyUpdateOpen(false)}
                disabled={dependencyUpdateRunning}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={() => void handleDependencyUpdate()}
                disabled={dependencyUpdateRunning}
                className="rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {dependencyUpdateRunning
                  ? t('common.refreshing')
                  : t('common.refresh')}
              </button>
            </div>
          </div>
        </div>
      )}

      {cveOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="cve-explain-title"
            className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl dark:bg-slate-900"
          >
            <h2
              id="cve-explain-title"
              className="text-lg font-semibold text-slate-900 dark:text-slate-100"
            >
              {t('repo.cve.title', { id: cveTitle })}
            </h2>
            <div className="mt-4">
              {cveLoading ? (
                <p className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  {t('repo.cve.loading')}
                </p>
              ) : cveError ? (
                <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
                  {cveError}
                </p>
              ) : (
                <p className="whitespace-pre-line text-sm text-slate-700 dark:text-slate-300">
                  {cveText}
                </p>
              )}
            </div>
            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setCveOpen(false)}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {t('common.close')}
              </button>
            </div>
          </div>
        </div>
      )}

      {readmeOpen && (
        <ReadmeModal repositoryId={repositoryId} onClose={() => setReadmeOpen(false)} />
      )}

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-50 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-xl dark:bg-slate-100 dark:text-slate-900"
        >
          {toast}
        </div>
      )}
    </section>
  )
}

function DependencyBadge({
  report,
  t,
}: {
  report: DependencyEcosystemReport | null
  t: Translate
}) {
  let label = t('common.none')
  let className = 'bg-slate-100 text-slate-500 ring-slate-200'
  if (report?.status === 'no_manifest') {
    label = t('repo.dependencyStatus.noManifest')
  } else if (report?.status === 'parse_error') {
    label = t('repo.dependencyStatus.parseError')
    className = 'bg-red-100 text-red-800 ring-red-200'
  } else if (report?.status === 'unavailable') {
    label = t('common.notAvailable')
    className = 'bg-amber-100 text-amber-800 ring-amber-200'
  } else if (report?.status === 'ok' && report.outdated > 0) {
    label = t('repo.dependencyStatus.outdated', { count: report.outdated })
    className = 'bg-amber-100 text-amber-800 ring-amber-200'
  } else if (report?.status === 'ok') {
    label = t('repo.dependencyStatus.current')
    className = 'bg-emerald-100 text-emerald-800 ring-emerald-200'
  }

  return (
    <span
      data-testid="dependencies-status"
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}
    >
      {label}
    </span>
  )
}

type CounterTone = 'amber' | 'emerald' | 'slate'

function DependencyCounter({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone: CounterTone
}) {
  const toneClass =
    tone === 'amber'
      ? 'text-amber-700 dark:text-amber-300'
      : tone === 'emerald'
        ? 'text-emerald-700 dark:text-emerald-300'
        : 'text-slate-600 dark:text-slate-300'
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800/50">
      <p className={`text-lg font-semibold ${toneClass}`}>{value}</p>
      <p className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </p>
    </div>
  )
}

function DependencyPackageRow({
  item,
  ecosystem,
  t,
}: {
  item: DependencyPackage
  ecosystem: 'python' | 'node'
  t: Translate
}) {
  const statusClass =
    item.status === 'outdated'
      ? 'bg-amber-100 text-amber-800'
      : item.status === 'current'
        ? 'bg-emerald-100 text-emerald-800'
        : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200'
  const severityClass =
    item.severity === 'major'
      ? 'bg-red-100 text-red-800'
      : item.severity === 'minor'
        ? 'bg-amber-100 text-amber-800'
        : 'bg-slate-100 text-slate-600'
  const projectUrl =
    ecosystem === 'python'
      ? `https://pypi.org/project/${encodeURIComponent(item.name)}/`
      : `https://www.npmjs.com/package/${encodeURIComponent(item.name)}`
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
      <div className="min-w-0">
        <a
          href={projectUrl}
          target="_blank"
          rel="noreferrer"
          className="font-mono text-sm font-medium text-primary hover:underline"
        >
          {item.name}
        </a>
        <p
          className="truncate font-mono text-[11px] text-slate-500 dark:text-slate-400"
          title={item.manifest_path ? `${item.declared} · ${item.manifest_path}` : item.declared}
        >
          {item.declared}
        </p>
        {item.manifest_path && (
          <p className="truncate font-mono text-[10px] text-slate-400 dark:text-slate-500">
            {item.manifest_path}
          </p>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="font-mono text-slate-600 dark:text-slate-300">
          {item.current ?? '—'} → {item.latest ?? '—'}
        </span>
        {item.severity && (
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${severityClass}`}>
            {t(`repo.severity.${item.severity}` as 'repo.severity.major')}
          </span>
        )}
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${statusClass}`}>
          {t(`repo.packageStatus.${item.status}` as 'repo.packageStatus.outdated')}
        </span>
      </div>
    </li>
  )
}

function dependencyErrorMessage(code: string | null, t: Translate): string {
  switch (code) {
    case 'rate_limited':
      return t('repo.dependencyError.rateLimited')
    case 'timeout':
      return t('repo.dependencyError.timeout')
    case 'registry_unavailable':
      return t('repo.dependencyError.registryUnavailable')
    case 'node_not_implemented':
      return t('repo.dependencyError.nodeNotImplemented')
    default:
      return code ?? t('repo.dependencyError.unavailable')
  }
}

function dependencySourceLabel(
  source: DependencyEcosystemReport['source'],
  t: Translate,
): string {
  switch (source) {
    case 'registry':
      return 'PyPI'
    case 'cache':
      return t('repo.dependencySource.cache')
    case 'mixed':
      return t('repo.dependencySource.mixed')
    case 'stale_cache':
      return t('repo.dependencySource.staleCache')
    default:
      return '—'
  }
}

function insightsNotice(report: InsightsReport, t: Translate): string | null {
  switch (report.status) {
    case 'timeout':
      return t('repo.insights.timeout')
    case 'unavailable':
      return t('repo.insights.unavailable')
    case 'no_branch':
      return t('repo.insights.noBranch')
    case 'shallow_clone':
      return t('repo.insights.shallowClone')
    case 'partial':
      return t('repo.insights.partial')
    default:
      return null
  }
}

function SecurityBadge({
  report,
  hasCritical,
  secrets,
  t,
}: {
  report: SecurityReport | null
  hasCritical: boolean
  secrets: number
  t: Translate
}) {
  if (report === null) {
    return (
      <span
        data-testid="security-status"
        className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-500 ring-1 ring-inset ring-slate-200"
      >
        {t('common.none')}
      </span>
    )
  }
  if (report.status === 'unavailable') {
    return (
      <span
        data-testid="security-status"
        className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-inset ring-amber-200"
      >
        {t('common.notAvailable')}
      </span>
    )
  }
  if (hasCritical || secrets > 0) {
    const parts: string[] = []
    if (hasCritical) {
      parts.push(`${report.summary.critical + report.summary.high} high/critical`)
    }
    if (secrets > 0) {
      parts.push(t('repo.security.secretsBadge', { count: secrets }))
    }
    return (
      <span
        data-testid="security-status"
        className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 ring-1 ring-inset ring-red-200"
      >
        {parts.join(' · ')}
      </span>
    )
  }
  return (
    <span
      data-testid="security-status"
      className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 ring-1 ring-inset ring-emerald-200"
    >
      {t('repo.security.cleanBadge')}
    </span>
  )
}

function SecurityVulnerabilityRow({
  item,
  t,
  onExplain,
}: {
  item: SecurityVulnerability
  t: Translate
  onExplain?: () => void
}) {
  const osvUrl = `https://osv.dev/vulnerability/${encodeURIComponent(item.osv_id)}`
  return (
    <li className="px-3 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <span className="font-mono text-sm font-medium text-slate-800 dark:text-slate-100">
            {item.package}
          </span>
          <span className="ml-2 font-mono text-xs text-slate-500 dark:text-slate-400">
            {item.version}
          </span>
          {item.version_source === 'lower_bound' && (
            <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              {t('repo.security.range')}
            </span>
          )}
        </div>
        <span
          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${securitySeverityClass(
            item.severity,
          )}`}
        >
          {item.severity}
        </span>
      </div>
      {item.summary && (
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
          {item.summary}
        </p>
      )}
      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
        <a
          href={osvUrl}
          target="_blank"
          rel="noreferrer"
          className="font-mono font-medium text-primary hover:underline"
        >
          {item.osv_id}
        </a>
        {item.cve_ids.map((cve) => (
          <a
            key={cve}
            href={`https://osv.dev/vulnerability/${encodeURIComponent(cve)}`}
            target="_blank"
            rel="noreferrer"
            className="font-mono text-slate-500 hover:underline dark:text-slate-400"
          >
            {cve}
          </a>
        ))}
        {item.fixed_version && (
          <span className="text-slate-500 dark:text-slate-400">
            {t('repo.security.fixedIn', { version: item.fixed_version })}
          </span>
        )}
        {onExplain && (
          <button
            type="button"
            onClick={onExplain}
            className="ml-auto rounded-md border border-slate-300 px-2 py-0.5 text-[11px] font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {t('repo.security.explain')}
          </button>
        )}
      </div>
    </li>
  )
}

function securitySeverityClass(severity: SecurityVulnerability['severity']): string {
  switch (severity) {
    case 'critical':
      return 'bg-red-100 text-red-800'
    case 'high':
      return 'bg-orange-100 text-orange-800'
    case 'medium':
      return 'bg-amber-100 text-amber-800'
    case 'low':
      return 'bg-yellow-100 text-yellow-800'
    default:
      return 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200'
  }
}

function secretTypeLabel(type: SecretFinding['type'], t: Translate): string {
  switch (type) {
    case 'aws_access_key':
      return t('repo.secretType.awsAccessKey')
    case 'aws_secret_key':
      return t('repo.secretType.awsSecretKey')
    case 'github_token':
      return t('repo.secretType.githubToken')
    case 'jwt':
      return t('repo.secretType.jwt')
    case 'private_key':
      return t('repo.secretType.privateKey')
    default:
      return type
  }
}

function DockerBadge({
  status,
  t,
}: {
  status: DockerStatus['status'] | undefined
  t: Translate
}) {
  const config =
    status === 'running'
      ? { label: t('repo.docker.status.running'), className: 'bg-emerald-100 text-emerald-800 ring-emerald-200' }
      : status === 'stopped'
        ? { label: t('repo.docker.status.stopped'), className: 'bg-slate-100 text-slate-600 ring-slate-200' }
        : status === 'unavailable'
          ? { label: t('repo.docker.status.unavailable'), className: 'bg-amber-100 text-amber-800 ring-amber-200' }
          : status === 'not_found'
            ? { label: t('repo.docker.status.notFound'), className: 'bg-slate-100 text-slate-500 ring-slate-200' }
            : { label: t('repo.docker.status.unknown'), className: 'bg-slate-100 text-slate-500 ring-slate-200' }

  return (
    <span
      data-testid="docker-status"
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${config.className}`}
    >
      {config.label}
    </span>
  )
}

function formatPort(port: DockerPort): string {
  const target = `${port.container_port ?? '?'}/${port.protocol}`
  if (port.host_port === null) {
    return target
  }
  return `${port.host_ip ?? '0.0.0.0'}:${port.host_port}->${target}`
}

function formatContainerPorts(container: DockerContainer, t: Translate): string {
  if (container.ports.length === 0) {
    return t('repo.docker.noPorts')
  }
  return container.ports.map(formatPort).join(', ')
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
  t,
}: {
  name: string
  info: MirrorProviderStatus | null
  fullName: string | null
  t: Translate
}) {
  const { formatDate } = useI18n()
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 p-3 text-sm">
      <p className="font-semibold text-slate-700 dark:text-slate-300">{name}</p>
      <p className="truncate text-xs text-slate-500 dark:text-slate-400" title={info?.full_name ?? fullName ?? ''}>
        {info?.full_name ?? fullName ?? t('repo.mirror.notConfigured')}
      </p>
      <p className="mt-2 font-mono text-xs text-slate-700 dark:text-slate-300">
        {info?.head_sha ? info.head_sha.slice(0, 12) : '—'}
      </p>
      <p className="text-xs text-slate-500 dark:text-slate-400">branch: {info?.branch ?? '—'}</p>
      <p className="text-xs text-slate-500 dark:text-slate-400">checked: {formatDate(info?.checked_at)}</p>
    </div>
  )
}
