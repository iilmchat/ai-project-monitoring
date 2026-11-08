import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'

import {
  activateAIProvider,
  deleteAIProvider,
  getAIProviders,
  getSettings,
  testLlm,
  updateSettings,
} from '../api/client'
import type {
  AIProviderProfile,
  AppSettings,
  LLMTestResult,
} from '../api/types'
import { useI18n } from '../i18n'
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
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [scanRoots, setScanRoots] = useState('')
  const [githubToken, setGithubToken] = useState('')
  const [gitflicToken, setGitflicToken] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [provider, setProvider] = useState<'github' | 'gitflic'>('github')
  const [providers, setProviders] = useState<AIProviderProfile[]>([])
  const [providersLoading, setProvidersLoading] = useState(true)
  const [providerModal, setProviderModal] = useState<{
    profile: AIProviderProfile | null
  } | null>(null)
  const [llmTesting, setLlmTesting] = useState(false)
  const [llmTest, setLlmTest] = useState<LLMTestResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
      }
      if (githubToken.trim()) payload.github_token = githubToken.trim()
      if (gitflicToken.trim()) payload.gitflic_token = gitflicToken.trim()
      if (webhookSecret.trim()) payload.webhook_secret = webhookSecret.trim()

      const updated = await updateSettings(payload)
      setSettings(updated)
      setGithubToken('')
      setGitflicToken('')
      setWebhookSecret('')
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
              onClick={() => setProviderModal({ profile: null })}
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
                      </div>
                      <p className="mt-1 font-mono text-xs text-slate-500 dark:text-slate-400">
                        {item.model_name}
                      </p>
                      <p className="truncate font-mono text-xs text-slate-400 dark:text-slate-500">
                        {item.base_url}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
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
            onClose={() => setProviderModal(null)}
            onSaved={handleProviderSaved}
          />
        </Suspense>
      )}
    </section>
  )
}
