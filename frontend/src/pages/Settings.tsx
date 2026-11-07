import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'

import { getSettings, updateSettings } from '../api/client'
import type { AppSettings } from '../api/types'
import { useI18n } from '../i18n'
import { useTableStore } from '../store/useTableStore'
import { useViewsStore } from '../store/useViewsStore'
import {
  WORKSPACE_FILENAME,
  buildWorkspace,
  downloadWorkspace,
  parseWorkspace,
} from '../utils/workspace'

export default function SettingsPage() {
  const { t } = useI18n()
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [scanRoots, setScanRoots] = useState('')
  const [githubToken, setGithubToken] = useState('')
  const [gitflicToken, setGitflicToken] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [provider, setProvider] = useState<'github' | 'gitflic'>('github')
  const [llmEnabled, setLlmEnabled] = useState(false)
  const [llmBaseUrl, setLlmBaseUrl] = useState('http://127.0.0.1:1234/v1')
  const [llmModel, setLlmModel] = useState('qwen2.5-coder-7b-instruct')
  const [llmApiKey, setLlmApiKey] = useState('')
  const [llmTimeout, setLlmTimeout] = useState(30)
  const [llmMaxDiffChars, setLlmMaxDiffChars] = useState(10000)
  const [llmAllowRemote, setLlmAllowRemote] = useState(false)
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
    void getSettings()
      .then((data) => {
        if (!active) return
        setSettings(data)
        setScanRoots(data.scan_roots)
        setProvider(data.default_canonical_provider === 'gitflic' ? 'gitflic' : 'github')
        setLlmEnabled(data.llm_enabled)
        setLlmBaseUrl(data.llm_base_url)
        setLlmModel(data.llm_model)
        setLlmTimeout(data.llm_timeout_seconds)
        setLlmMaxDiffChars(data.llm_max_diff_chars)
        setLlmAllowRemote(data.llm_allow_remote)
      })
      .catch(() => {
        if (active) setError(t('settings.loadError'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setMessage(null)
    try {
      const payload: Record<string, unknown> = {
        scan_roots: scanRoots,
        default_canonical_provider: provider,
        llm_enabled: llmEnabled,
        llm_base_url: llmBaseUrl.trim(),
        llm_model: llmModel.trim(),
        llm_timeout_seconds: llmTimeout,
        llm_max_diff_chars: llmMaxDiffChars,
        llm_allow_remote: llmAllowRemote,
      }
      if (githubToken.trim()) payload.github_token = githubToken.trim()
      if (gitflicToken.trim()) payload.gitflic_token = gitflicToken.trim()
      if (webhookSecret.trim()) payload.webhook_secret = webhookSecret.trim()
      if (llmApiKey.trim()) payload.llm_api_key = llmApiKey.trim()

      const updated = await updateSettings(payload)
      setSettings(updated)
      setGithubToken('')
      setGitflicToken('')
      setWebhookSecret('')
      setLlmApiKey('')
      setMessage(t('settings.saved'))
      setError(null)
    } catch {
      setError(t('settings.saveError'))
    } finally {
      setSaving(false)
    }
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

          <div className="space-y-3 rounded-lg border border-slate-200 p-4 dark:border-slate-700">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                {t('settings.aiSection')}
              </h2>
              <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={llmEnabled}
                  onChange={(event) => setLlmEnabled(event.target.checked)}
                />
                {t('settings.enableAi')}
              </label>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.endpoint')}
                <input
                  value={llmBaseUrl}
                  onChange={(event) => setLlmBaseUrl(event.target.value)}
                  placeholder="http://127.0.0.1:1234/v1"
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.model')}
                <input
                  value={llmModel}
                  onChange={(event) => setLlmModel(event.target.value)}
                  placeholder="qwen2.5-coder-7b-instruct"
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.apiKey')}
                <input
                  type="password"
                  value={llmApiKey}
                  onChange={(event) => setLlmApiKey(event.target.value)}
                  placeholder={settings?.llm_api_key || 'не задан'}
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  {t('settings.timeout')}
                  <input
                    type="number"
                    min={1}
                    max={300}
                    value={llmTimeout}
                    onChange={(event) => setLlmTimeout(Number(event.target.value))}
                    className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                  />
                </label>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  {t('settings.maxDiff')}
                  <input
                    type="number"
                    min={100}
                    max={100000}
                    value={llmMaxDiffChars}
                    onChange={(event) =>
                      setLlmMaxDiffChars(Number(event.target.value))
                    }
                    className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                  />
                </label>
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={llmAllowRemote}
                onChange={(event) => setLlmAllowRemote(event.target.checked)}
              />
              {t('settings.allowRemote')}
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
    </section>
  )
}
