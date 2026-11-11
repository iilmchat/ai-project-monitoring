import { useState } from 'react'
import type { FormEvent } from 'react'

import {
  authorizeGigaChat,
  createAIProvider,
  updateAIProvider,
} from '../api/client'
import type { AIProviderProfile } from '../api/types'
import { useI18n } from '../i18n'

type ProviderType = 'openai_compatible' | 'gigachat'

interface AIProviderModalProps {
  profile: AIProviderProfile | null
  initialProviderType?: ProviderType
  onClose: () => void
  onSaved: () => void
}

const GIGACHAT_BASE_URL = 'https://gigachat.devices.sberbank.ru/api/v1'

export default function AIProviderModal({
  profile,
  initialProviderType,
  onClose,
  onSaved,
}: AIProviderModalProps) {
  const { t } = useI18n()
  const editing = profile !== null
  const [providerType, setProviderType] = useState<ProviderType>(
    profile?.provider_type ?? initialProviderType ?? 'openai_compatible',
  )
  const [name, setName] = useState(profile?.name ?? '')
  const [baseUrl, setBaseUrl] = useState(
    profile?.base_url ??
      (providerType === 'gigachat'
        ? GIGACHAT_BASE_URL
        : 'http://127.0.0.1:1234/v1'),
  )
  const [modelName, setModelName] = useState(
    profile?.model_name ??
      (providerType === 'gigachat' ? 'GigaChat' : 'qwen2.5-coder-7b-instruct'),
  )
  const [embeddingModel, setEmbeddingModel] = useState(
    profile?.embedding_model ??
      (providerType === 'gigachat'
        ? ''
        : 'text-embedding-nomic-embed-text-v1.5'),
  )
  const [apiKey, setApiKey] = useState('')
  const [clientId, setClientId] = useState(profile?.client_id ?? '')
  const [clientSecret, setClientSecret] = useState('')
  const [scope, setScope] = useState(
    profile?.oauth_scope ?? 'GIGACHAT_API_PERS',
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function changeProviderType(next: ProviderType) {
    setProviderType(next)
    if (next === 'gigachat') {
      if (!baseUrl || baseUrl === 'http://127.0.0.1:1234/v1') {
        setBaseUrl(GIGACHAT_BASE_URL)
      }
      if (!modelName || modelName === 'qwen2.5-coder-7b-instruct') {
        setModelName('GigaChat')
      }
    }
    if (next === 'openai_compatible' && !embeddingModel) {
      setEmbeddingModel('text-embedding-nomic-embed-text-v1.5')
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      if (providerType === 'gigachat') {
        await authorizeGigaChat({
          client_id: clientId.trim(),
          client_secret: clientSecret.trim(),
          scope: scope.trim() || 'GIGACHAT_API_PERS',
          model_name: modelName.trim(),
          profile_name: name.trim(),
          base_url: baseUrl.trim() || undefined,
          activate: true,
        })
      } else {
        const payload = {
          name: name.trim(),
          base_url: baseUrl.trim(),
          model_name: modelName.trim(),
          embedding_model: embeddingModel.trim(),
          api_key: apiKey.trim() || undefined,
          provider_type: providerType,
        }
        if (editing) {
          await updateAIProvider(profile.id, payload)
        } else {
          await createAIProvider(payload)
        }
      }
      onSaved()
      onClose()
    } catch {
      setError(
        providerType === 'gigachat'
          ? t('settings.gigachatAuthError')
          : t('settings.providerSaveError'),
      )
    } finally {
      setSaving(false)
    }
  }

  const canSubmit =
    name.trim() &&
    baseUrl.trim() &&
    modelName.trim() &&
    (providerType !== 'gigachat' || (clientId.trim() && clientSecret.trim()))

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
        className="max-h-full w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-2xl dark:bg-slate-900"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          {editing ? t('settings.edit') : t('settings.addProvider')}
        </h2>
        <div className="mt-4 space-y-3">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            {t('settings.providerType')}
            <select
              value={providerType}
              onChange={(event) =>
                changeProviderType(event.target.value as ProviderType)
              }
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            >
              <option value="openai_compatible">
                {t('settings.providerTypeOpenai')}
              </option>
              <option value="gigachat">{t('settings.providerTypeGigachat')}</option>
            </select>
          </label>
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
            {providerType === 'gigachat'
              ? t('settings.gigachatBaseUrl')
              : t('settings.providerBaseUrl')}
            <input
              required
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder={GIGACHAT_BASE_URL}
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
          {providerType === 'openai_compatible' && (
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              {t('settings.providerEmbeddingModel')}
              <input
                value={embeddingModel}
                onChange={(event) => setEmbeddingModel(event.target.value)}
                placeholder="text-embedding-nomic-embed-text-v1.5"
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
              <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">
                {t('settings.providerEmbeddingModelHint')}
              </span>
            </label>
          )}

          {providerType === 'gigachat' ? (
            <>
              <p className="rounded-md bg-sky-50 px-3 py-2 text-xs text-sky-800 dark:bg-sky-900/30 dark:text-sky-200">
                {t('settings.gigachatHint')}
              </p>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.gigachatClientId')}
                <input
                  required
                  value={clientId}
                  onChange={(event) => setClientId(event.target.value)}
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.gigachatClientSecret')}
                <input
                  required
                  type="password"
                  value={clientSecret}
                  onChange={(event) => setClientSecret(event.target.value)}
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('settings.gigachatScope')}
                <input
                  value={scope}
                  onChange={(event) => setScope(event.target.value)}
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
            </>
          ) : (
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
          )}
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
            disabled={saving || !canSubmit}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-container disabled:opacity-50"
          >
            {saving
              ? providerType === 'gigachat'
                ? t('settings.gigachatAuthorizing')
                : t('common.saving')
              : providerType === 'gigachat'
                ? t('settings.gigachatAuthorize')
                : editing
                  ? t('settings.saveProvider')
                  : t('settings.createProvider')}
          </button>
        </div>
      </form>
    </div>
  )
}
