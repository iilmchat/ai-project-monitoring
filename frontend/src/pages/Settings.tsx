import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'

import {
  activateAIProvider,
  deleteAIProvider,
  getAIProviders,
  getSettings,
  refreshGigaChatToken,
  testLlm,
  updateSettings,
} from '../api/client'
import type {
  AIProviderProfile,
  AppSettings,
  LLMTestResult,
} from '../api/types'
import { isTauri, openLogsFolder } from '../desktop/tauri'
import { checkForUpdates, installUpdate, relaunchApp } from '../desktop/updater'
import type { Update } from '../desktop/updater'
import { useI18n, useI18nNamespace } from '../i18n'
import { useTableStore } from '../store/useTableStore'
import { useViewsStore } from '../store/useViewsStore'
import {
  WORKSPACE_FILENAME,
  buildWorkspace,
  downloadWorkspace,
  parseWorkspace,
} from '../utils/workspace'

const AIProviderModal = lazy(() => import('../components/AIProviderModal'))

export default function SettingsPage() {
  const { t } = useI18n()
  const dictionaryReady = useI18nNamespace('settings')

  if (!dictionaryReady) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
  }

  return <SettingsContent />
}

function SettingsContent() {
  const { t, formatDate } = useI18n()
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [scanRoots, setScanRoots] = useState('')
  const [githubToken, setGithubToken] = useState('')
  const [gitflicToken, setGitflicToken] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [telegramToken, setTelegramToken] = useState('')
  const [telegramChatId, setTelegramChatId] = useState('')
  const [notificationsEnabled, setNotificationsEnabled] = useState(true)
  const [fetchTimeout, setFetchTimeout] = useState(30)
  const [statusTtl, setStatusTtl] = useState(60)
  const [mirrorPoll, setMirrorPoll] = useState(300)
  const [provider, setProvider] = useState<'github' | 'gitflic'>('github')
  const [providers, setProviders] = useState<AIProviderProfile[]>([])
  const [providersLoading, setProvidersLoading] = useState(true)
  const [providerModal, setProviderModal] = useState<{
    profile: AIProviderProfile | null
    initialProviderType?: 'openai_compatible' | 'gigachat'
  } | null>(null)
  const [llmTesting, setLlmTesting] = useState(false)
  const [llmTest, setLlmTest] = useState<LLMTestResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [logsError, setLogsError] = useState<string | null>(null)
  const [updateChecking, setUpdateChecking] = useState(false)
  const [availableUpdate, setAvailableUpdate] = useState<Update | null>(null)
  const [updateInstalling, setUpdateInstalling] = useState(false)
  const [updateProgress, setUpdateProgress] = useState(0)
  const [updateError, setUpdateError] = useState<string | null>(null)
  const [updateToast, setUpdateToast] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const updateToastTimer = useRef<number | null>(null)

  const desktop = isTauri()
  const viewsExport = useViewsStore((state) => state.getExportState)
  const importViews = useViewsStore((state) => state.importState)
  const tableExport = useTableStore((state) => state.getExportState)
  const importTable = useTableStore((state) => state.importState)

  useEffect(() => {
    let active = true
    void Promise.all([getSettings(), getAIProviders()])
      .then(([data, providerData]) => {
        if (!active) return
        setSettings(data)
        setScanRoots(data.scan_roots)
        setProvider(data.default_canonical_provider === 'gitflic' ? 'gitflic' : 'github')
        setTelegramChatId(data.telegram_chat_id ?? '')
        setNotificationsEnabled(data.notifications_enabled ?? true)
        setFetchTimeout(data.fetch_timeout ?? 30)
        setStatusTtl(data.status_ttl_seconds ?? 60)
        setMirrorPoll(data.mirror_poll_interval_seconds ?? 300)
        setProviders(providerData)
      })
      .catch(() => {
        if (active) setError(t('settings.loadError'))
      })
      .finally(() => {
        if (active) {
          setLoading(false)
          setProvidersLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [t])

  useEffect(
    () => () => {
      if (updateToastTimer.current !== null) {
        window.clearTimeout(updateToastTimer.current)
      }
    },
    [],
  )

  async function reloadProviders() {
    try {
      setProviders(await getAIProviders())
    } catch {
      setError(t('settings.loadError'))
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setMessage(null)
    try {
      const payload: Record<string, unknown> = {
        scan_roots: scanRoots,
        default_canonical_provider: provider,
        telegram_chat_id: telegramChatId,
        notifications_enabled: notificationsEnabled,
        fetch_timeout: fetchTimeout,
        status_ttl_seconds: statusTtl,
        mirror_poll_interval_seconds: mirrorPoll,
      }
      if (githubToken.trim()) payload.github_token = githubToken.trim()
      if (gitflicToken.trim()) payload.gitflic_token = gitflicToken.trim()
      if (webhookSecret.trim()) payload.webhook_secret = webhookSecret.trim()
      if (telegramToken.trim()) payload.telegram_bot_token = telegramToken.trim()

      const updated = await updateSettings(payload)
      setSettings(updated)
      setGithubToken('')
      setGitflicToken('')
      setWebhookSecret('')
      setTelegramToken('')
      setMessage(t('settings.saved'))
      setError(null)
    } catch {
      setError(t('settings.saveError'))
    } finally {
      setSaving(false)
    }
  }

  async function handleTestLlm() {
    setLlmTesting(true)
    try {
      setLlmTest(await testLlm())
    } catch {
      setLlmTest({ status: 'error', latency_ms: 0, error: 'request_failed' })
    } finally {
      setLlmTesting(false)
    }
  }

  async function handleActivate(profile: AIProviderProfile) {
    try {
      await activateAIProvider(profile.id)
      await reloadProviders()
      setLlmTest(null)
      setMessage(t('settings.providerUpdated', { name: profile.name }))
      setError(null)
    } catch {
      setError(t('settings.providerSaveError'))
    }
  }

  async function handleDelete(profile: AIProviderProfile) {
    if (!window.confirm(t('settings.providerDeleteConfirm', { name: profile.name }))) {
      return
    }
    try {
      await deleteAIProvider(profile.id)
      await reloadProviders()
      setMessage(t('settings.providerUpdated', { name: profile.name }))
      setError(null)
    } catch {
      setError(t('settings.providerSaveError'))
    }
  }

  function handleProviderSaved() {
    void reloadProviders()
    setLlmTest(null)
  }

  async function handleRefreshGigaChat(item: AIProviderProfile) {
    try {
      await refreshGigaChatToken(item.id)
      await reloadProviders()
      setMessage(t('settings.gigachatRefreshed'))
      setError(null)
    } catch {
      setError(t('settings.gigachatAuthError'))
    }
  }

  async function handleOpenLogs() {
    setLogsError(null)
    try {
      await openLogsFolder()
    } catch {
      setLogsError(t('settings.openLogsError'))
    }
  }

  function showUpdateToast(text: string) {
    setUpdateToast(text)
    if (updateToastTimer.current !== null) {
      window.clearTimeout(updateToastTimer.current)
    }
    updateToastTimer.current = window.setTimeout(() => {
      setUpdateToast(null)
      updateToastTimer.current = null
    }, 4000)
  }

  async function handleCheckUpdates() {
    setUpdateChecking(true)
    setUpdateError(null)
    setUpdateToast(null)
    try {
      const update = await checkForUpdates()
      if (update) {
        setAvailableUpdate(update)
      } else {
        showUpdateToast(t('settings.upToDate'))
      }
    } catch {
      setUpdateError(t('settings.updateCheckError'))
    } finally {
      setUpdateChecking(false)
    }
  }

  async function handleInstallUpdate() {
    if (!availableUpdate) {
      return
    }
    setUpdateInstalling(true)
    setUpdateProgress(0)
    setUpdateError(null)
    try {
      await installUpdate(availableUpdate, setUpdateProgress)
      await relaunchApp()
    } catch {
      setUpdateError(t('settings.updateInstallError'))
      setUpdateInstalling(false)
    }
  }

  function dismissUpdate() {
    if (updateInstalling) {
      return
    }
    void availableUpdate?.close()
    setAvailableUpdate(null)
    setUpdateProgress(0)
    setUpdateError(null)
  }

  function handleExportWorkspace() {
    const workspace = buildWorkspace({
      views: viewsExport().views,
      table: tableExport(),
    })
    downloadWorkspace(workspace)
    setMessage(t('settings.workspaceExported', { filename: WORKSPACE_FILENAME }))
    setError(null)
  }

  async function handleImportWorkspace(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    try {
      if (file.size > 1024 * 1024) {
        throw new Error('workspace file is too large')
      }
      const parsed = parseWorkspace(JSON.parse(await file.text()))
      importViews({ version: 1, views: parsed.views })
      importTable({
        version: 1,
        visibleColumns: parsed.table.visible_columns,
        columnWidths: parsed.table.column_widths,
      })
      setMessage(t('settings.workspaceImported'))
      setError(null)
    } catch {
      setError(t('settings.workspaceImportError'))
    } finally {
      event.target.value = ''
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('settings.title')}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t('settings.subtitle')}
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/40 dark:text-red-300">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
          {message}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : (
        <form
          onSubmit={(event) => void handleSubmit(event)}
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            {t('settings.scanRoots')}
            <textarea
              value={scanRoots}
              onChange={(event) => setScanRoots(event.target.value)}
              rows={3}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              GITHUB_TOKEN
              <input
                type="password"
                value={githubToken}
                onChange={(event) => setGithubToken(event.target.value)}
                placeholder={settings?.github_token || t('common.notSet')}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              GITFLIC_TOKEN
              <input
                type="password"
                value={gitflicToken}
                onChange={(event) => setGitflicToken(event.target.value)}
                placeholder={settings?.gitflic_token || t('common.notSet')}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              WEBHOOK_SECRET
              <input
                type="password"
                value={webhookSecret}
                onChange={(event) => setWebhookSecret(event.target.value)}
                placeholder={settings?.webhook_secret || t('common.notSet')}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              {t('settings.canonicalProvider')}
              <select
                value={provider}
                onChange={(event) =>
                  setProvider(event.target.value === 'gitflic' ? 'gitflic' : 'github')
                }
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              >
                <option value="github">GitHub</option>
                <option value="gitflic">GitFlic</option>
              </select>
            </label>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400">
            {t('settings.tokenHint')}
          </p>

          <div className="border-t border-slate-200 pt-4 dark:border-slate-700">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {t('settings.notificationsSection')}
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {t('settings.notificationsHint')}
            </p>
            <label className="mt-3 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={notificationsEnabled}
                onChange={(event) => setNotificationsEnabled(event.target.checked)}
              />
              {t('settings.notificationsEnabled')}
            </label>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.telegramToken')}
                <input
                  type="password"
                  value={telegramToken}
                  onChange={(event) => setTelegramToken(event.target.value)}
                  placeholder={settings?.telegram_bot_token || t('common.notSet')}
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.telegramChatId')}
                <input
                  value={telegramChatId}
                  onChange={(event) => setTelegramChatId(event.target.value)}
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
            </div>
          </div>

          <div className="border-t border-slate-200 pt-4 dark:border-slate-700">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {t('settings.performanceSection')}
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {t('settings.performanceHint')}
            </p>
            <div className="mt-3 grid gap-4 md:grid-cols-3">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.fetchTimeout')}
                <input
                  type="number"
                  min={1}
                  value={fetchTimeout}
                  onChange={(event) =>
                    setFetchTimeout(Number(event.target.value) || 1)
                  }
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.statusTtl')}
                <input
                  type="number"
                  min={1}
                  value={statusTtl}
                  onChange={(event) =>
                    setStatusTtl(Number(event.target.value) || 1)
                  }
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.mirrorPollInterval')}
                <input
                  type="number"
                  min={1}
                  value={mirrorPoll}
                  onChange={(event) =>
                    setMirrorPoll(Number(event.target.value) || 1)
                  }
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? t('common.saving') : t('common.save')}
            </button>
          </div>
        </form>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              {t('settings.aiProviders')}
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {t('settings.aiProvidersHint')}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void handleTestLlm()}
              disabled={llmTesting}
              className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {llmTesting ? t('settings.testingLlm') : t('settings.testLlm')}
            </button>
            <button
              type="button"
              onClick={() =>
                setProviderModal({
                  profile: null,
                  initialProviderType: 'gigachat',
                })
              }
              className="rounded-md border border-sky-300 px-3 py-1 text-sm font-medium text-sky-700 hover:bg-sky-50 dark:border-sky-700 dark:text-sky-300 dark:hover:bg-sky-900/20"
            >
              {t('settings.gigachatAuth')}
            </button>
            <button
              type="button"
              onClick={() =>
                setProviderModal({
                  profile: null,
                  initialProviderType: 'openai_compatible',
                })
              }
              className="rounded-md bg-primary px-3 py-1 text-sm font-medium text-white hover:bg-primary-container"
            >
              {t('settings.addProvider')}
            </button>
          </div>
        </div>

        {llmTest && (
          <p
            className={`mt-3 rounded-md px-3 py-2 text-sm ${
              llmTest.status === 'ok'
                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200'
                : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-200'
            }`}
          >
            {llmTest.status === 'ok'
              ? `${t('settings.llmOk')} · ${t('settings.llmLatency', {
                  ms: Math.round(llmTest.latency_ms),
                })}`
              : `${t('settings.llmError')}${llmTest.error ? ` (${llmTest.error})` : ''}`}
          </p>
        )}

        <div className="mt-4">
          {providersLoading ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t('settings.providerLoading')}
            </p>
          ) : providers.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t('settings.providerEmpty')}
            </p>
          ) : (
            <ul className="space-y-3">
              {providers.map((item) => (
                <li
                  key={item.id}
                  className="rounded-lg border border-slate-200 p-4 dark:border-slate-700"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium text-slate-900 dark:text-slate-100">
                          {item.name}
                        </p>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            item.is_active
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200'
                              : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                          }`}
                          title={
                            item.is_active
                              ? t('settings.providerActiveHint')
                              : undefined
                          }
                        >
                          {item.is_active
                            ? t('settings.providerActive')
                            : t('settings.providerInactive')}
                        </span>
                        {item.provider_type === 'gigachat' && (
                          <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] font-medium text-sky-800 dark:bg-sky-900/40 dark:text-sky-200">
                            {t('settings.gigachatBadge')}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 font-mono text-xs text-slate-500 dark:text-slate-400">
                        {item.model_name}
                      </p>
                      <p className="truncate font-mono text-xs text-slate-400 dark:text-slate-500">
                        {item.base_url}
                      </p>
                      {item.provider_type === 'gigachat' &&
                        item.oauth_expires_at && (
                          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                            {t('settings.gigachatTokenUntil', {
                              date: formatDate(item.oauth_expires_at),
                            })}
                          </p>
                        )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {item.provider_type === 'gigachat' && (
                        <button
                          type="button"
                          onClick={() => void handleRefreshGigaChat(item)}
                          className="rounded-md border border-sky-300 px-3 py-1 text-xs font-medium text-sky-700 hover:bg-sky-50 dark:border-sky-700 dark:text-sky-300 dark:hover:bg-sky-900/20"
                        >
                          {t('settings.gigachatRefresh')}
                        </button>
                      )}
                      {!item.is_active && (
                        <button
                          type="button"
                          onClick={() => void handleActivate(item)}
                          className="rounded-md border border-emerald-300 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50 dark:border-emerald-700 dark:text-emerald-300 dark:hover:bg-emerald-900/20"
                        >
                          {t('settings.activate')}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setProviderModal({ profile: item })}
                        className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                      >
                        {t('settings.edit')}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDelete(item)}
                        className="rounded-md border border-red-200 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/20"
                      >
                        {t('settings.delete')}
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {desktop && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            {t('settings.updates')}
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {t('settings.updatesHint')}
          </p>
          {updateError && (
            <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">
              {updateError}
            </p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void handleCheckUpdates()}
              disabled={updateChecking || updateInstalling}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {updateChecking
                ? t('settings.checkingUpdates')
                : t('settings.checkUpdates')}
            </button>
          </div>
        </div>
      )}

      {desktop && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            {t('settings.diagnostics')}
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {t('settings.diagnosticsHint')}
          </p>
          {logsError && (
            <p className="mt-3 text-sm text-red-600 dark:text-red-400">
              {logsError}
            </p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void handleOpenLogs()}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {t('settings.openLogs')}
            </button>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          {t('settings.workspace')}
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {t('settings.workspaceHint')}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleExportWorkspace}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {t('settings.exportWorkspace')}
          </button>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {t('settings.importWorkspace')}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(event) => void handleImportWorkspace(event)}
          />
        </div>
        <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
          {t('settings.workspaceFormat', { filename: WORKSPACE_FILENAME })}
        </p>
      </div>

      {providerModal && (
        <Suspense fallback={null}>
          <AIProviderModal
            profile={providerModal.profile}
            initialProviderType={providerModal.initialProviderType}
            onClose={() => setProviderModal(null)}
            onSaved={handleProviderSaved}
          />
        </Suspense>
      )}

      {availableUpdate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="update-title"
            className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl dark:bg-slate-900"
          >
            <h2
              id="update-title"
              className="text-lg font-semibold text-slate-900 dark:text-slate-100"
            >
              {t('settings.updateAvailableTitle')}
            </h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              {t('settings.updateAvailableBody', {
                version: availableUpdate.version,
                current: availableUpdate.currentVersion,
              })}
            </p>
            {availableUpdate.body && (
              <p className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                {availableUpdate.body}
              </p>
            )}
            {updateInstalling && (
              <div className="mt-4">
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  {t('settings.updateProgress', { percent: updateProgress })}
                </p>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                  <div
                    className="h-full bg-primary transition-all"
                    style={{ width: `${updateProgress}%` }}
                  />
                </div>
              </div>
            )}
            {updateError && (
              <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">
                {updateError}
              </p>
            )}
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={dismissUpdate}
                disabled={updateInstalling}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {t('settings.updateLater')}
              </button>
              <button
                type="button"
                onClick={() => void handleInstallUpdate()}
                disabled={updateInstalling}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
              >
                {updateInstalling
                  ? t('settings.installingUpdate')
                  : t('settings.installUpdate')}
              </button>
            </div>
          </div>
        </div>
      )}

      {updateToast && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-50 rounded-lg bg-slate-900 px-4 py-3 text-sm text-white shadow-lg dark:bg-slate-100 dark:text-slate-900"
        >
          {updateToast}
        </div>
      )}
    </section>
  )
}
