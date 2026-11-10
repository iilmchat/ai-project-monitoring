import { useEffect, useState } from 'react'

import { generateAutomation } from '../api/client'
import type { AutomationConfig, AutomationTool } from '../api/types'
import { useI18n } from '../i18n'

export default function AutomationModal({
  repositoryId,
  open,
  onClose,
}: {
  repositoryId: number
  open: boolean
  onClose: () => void
}) {
  const { t } = useI18n()
  const [config, setConfig] = useState<AutomationConfig | null>(null)
  const [loading, setLoading] = useState<AutomationTool | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!open) {
      setConfig(null)
      setError(null)
      setCopied(false)
    }
  }, [open])

  if (!open) {
    return null
  }

  async function generate(tool: AutomationTool) {
    setLoading(tool)
    setError(null)
    setCopied(false)
    try {
      setConfig(await generateAutomation(repositoryId, tool))
    } catch {
      setError(t('repo.automation.error'))
    } finally {
      setLoading(null)
    }
  }

  async function copy() {
    if (!config) return
    try {
      await navigator.clipboard.writeText(config.content)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t('repo.automation.title')}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl dark:bg-slate-900"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              {t('repo.automation.title')}
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {t('repo.automation.subtitle')}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-3 py-1 text-sm dark:border-slate-600"
          >
            {t('common.close')}
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void generate('dependabot')}
            disabled={loading !== null}
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {loading === 'dependabot'
              ? t('repo.automation.generating')
              : t('repo.automation.dependabot')}
          </button>
          <button
            type="button"
            onClick={() => void generate('renovate')}
            disabled={loading !== null}
            className="rounded-md border border-primary px-3 py-2 text-sm font-medium text-primary disabled:opacity-60"
          >
            {loading === 'renovate'
              ? t('repo.automation.generating')
              : t('repo.automation.renovate')}
          </button>
        </div>

        {error && (
          <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
            {error}
          </p>
        )}

        {config && (
          <div className="mt-4 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span className="font-mono">{config.path}</span>
              <span>
                {t('repo.automation.ecosystems')}:{' '}
                {config.ecosystems.join(', ') || '-'}
              </span>
              <button
                type="button"
                onClick={() => void copy()}
                className="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-600"
              >
                {copied ? t('repo.automation.copied') : t('repo.automation.copy')}
              </button>
            </div>
            {config.warnings.length > 0 && (
              <p className="text-xs text-amber-700 dark:text-amber-300">
                {config.warnings.join(', ')}
              </p>
            )}
            <pre className="max-h-80 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">
              <code>{config.content}</code>
            </pre>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              {t('repo.automation.noCommit')}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
