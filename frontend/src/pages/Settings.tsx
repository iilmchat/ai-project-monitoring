import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'

import { getSettings, updateSettings } from '../api/client'
import type { AppSettings } from '../api/types'
import { useTableStore } from '../store/useTableStore'
import { useViewsStore } from '../store/useViewsStore'
import {
  WORKSPACE_FILENAME,
  buildWorkspace,
  downloadWorkspace,
  parseWorkspace,
} from '../utils/workspace'

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [scanRoots, setScanRoots] = useState('')
  const [githubToken, setGithubToken] = useState('')
  const [gitflicToken, setGitflicToken] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [provider, setProvider] = useState<'github' | 'gitflic'>('github')
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
      })
      .catch(() => {
        if (active) setError('Не удалось загрузить настройки.')
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
      const payload: Record<string, string> = {
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
      setMessage('Настройки сохранены.')
      setError(null)
    } catch {
      setError('Не удалось сохранить настройки.')
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
    setMessage(`Workspace экспортирован: ${WORKSPACE_FILENAME}`)
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
      setMessage('Настройки workspace импортированы.')
      setError(null)
    } catch {
      setError(
        'Не удалось импортировать настройки: неверный формат или версия файла.',
      )
    } finally {
      event.target.value = ''
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Настройки</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Значения сохраняются в БД и применяются без перезапуска.
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
        <p className="text-sm text-slate-500 dark:text-slate-400">Загрузка…</p>
      ) : (
        <form
          onSubmit={(event) => void handleSubmit(event)}
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            SCAN_ROOTS (пути через запятую)
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
                placeholder={settings?.github_token || 'не задан'}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              GITFLIC_TOKEN
              <input
                type="password"
                value={gitflicToken}
                onChange={(event) => setGitflicToken(event.target.value)}
                placeholder={settings?.gitflic_token || 'не задан'}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              WEBHOOK_SECRET
              <input
                type="password"
                value={webhookSecret}
                onChange={(event) => setWebhookSecret(event.target.value)}
                placeholder={settings?.webhook_secret || 'не задан'}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              Канонический провайдер по умолчанию
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
            Пустое поле токена означает «не менять». Маска показывает уже сохранённое значение.
          </p>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? 'Сохранение…' : 'Сохранить'}
            </button>
          </div>
        </form>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Workspace
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Экспорт и импорт UI-настроек: Saved Views, видимые колонки и их ширина.
          Токены и пути сканирования не экспортируются.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleExportWorkspace}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Экспорт настроек (JSON)
          </button>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Импорт настроек
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
          Формат: {WORKSPACE_FILENAME} · версия схемы 1 · до 1 MiB.
        </p>
      </div>
    </section>
  )
}
