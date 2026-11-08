import { useState } from 'react'
import type { FormEvent } from 'react'

import { createAIProvider, updateAIProvider } from '../api/client'
import type { AIProviderProfile } from '../api/types'
import { useI18n } from '../i18n'

interface AIProviderModalProps {
  profile: AIProviderProfile | null
  onClose: () => void
  onSaved: (profile: AIProviderProfile) => void
}

export default function AIProviderModal({
  profile,
  onClose,
  onSaved,
}: AIProviderModalProps) {
  const { t } = useI18n()
  const editing = profile !== null
  const [name, setName] = useState(profile?.name ?? '')
  const [baseUrl, setBaseUrl] = useState(
    profile?.base_url ?? 'http://127.0.0.1:1234/v1',
  )
  const [modelName, setModelName] = useState(
    profile?.model_name ?? 'qwen2.5-coder-7b-instruct',
  )
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = {
        name: name.trim(),
        base_url: baseUrl.trim(),
        model_name: modelName.trim(),
        api_key: apiKey.trim() || undefined,
      }
      const saved = editing
        ? await updateAIProvider(profile.id, payload)
        : await createAIProvider(payload)
      onSaved(saved)
      onClose()
    } catch {
      setError(t('settings.providerSaveError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={editing ? t('settings.edit') : t('settings.addProvider')}
      onClick={onClose}
    >
      <form
        onSubmit={(event) => void submit(event)}
        className="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl dark:bg-slate-900"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          {editing ? t('settings.edit') : t('settings.addProvider')}
        </h2>
        <div className="mt-4 space-y-3">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            {t('settings.providerName')}
            <input
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            {t('settings.providerBaseUrl')}
            <input
              required
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="http://127.0.0.1:1234/v1"
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            {t('settings.providerModel')}
            <input
              required
              value={modelName}
              onChange={(event) => setModelName(event.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            {t('settings.providerApiKey')}
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={editing ? profile.api_key || '' : ''}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
            <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">
              {t('settings.providerApiKeyHint')}
            </span>
          </label>
        </div>
        {error && (
          <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
            {error}
          </p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {t('common.cancel')}
          </button>
          <button
            type="submit"
            disabled={saving || !name.trim() || !baseUrl.trim() || !modelName.trim()}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-container disabled:opacity-50"
          >
            {saving
              ? t('common.saving')
              : editing
                ? t('settings.saveProvider')
                : t('settings.createProvider')}
          </button>
        </div>
      </form>
    </div>
  )
}
