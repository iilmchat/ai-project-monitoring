import { useEffect, useState } from 'react'

import { resolveConflict } from '../api/client'
import type { ConflictResolveResponse } from '../api/types'
import { useI18n } from '../i18n'
import MarkdownView from './MarkdownView'

interface ConflictResolverModalProps {
  repositoryId: number
  filePath: string
  onClose: () => void
}

export default function ConflictResolverModal({
  repositoryId,
  filePath,
  onClose,
}: ConflictResolverModalProps) {
  const { locale, t } = useI18n()
  const [result, setResult] = useState<ConflictResolveResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let active = true
    void resolveConflict(repositoryId, filePath, locale)
      .then((data) => {
        if (active) {
          setResult(data)
          setError(null)
        }
      })
      .catch(() => {
        if (active) {
          setError(t('repo.conflicts.resolveError'))
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [filePath, locale, repositoryId, t])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  async function copyResolved() {
    if (!result) {
      return
    }
    try {
      await navigator.clipboard.writeText(result.resolved)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setError(t('repo.conflicts.copyError'))
    }
  }

  const markdown = result ? `\`\`\`\n${result.resolved}\n\`\`\`` : ''

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t('repo.conflicts.aiTitle')}
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl dark:bg-slate-900"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t('repo.conflicts.aiTitle')}
            </h2>
            <p className="truncate font-mono text-xs text-slate-500 dark:text-slate-400" title={filePath}>
              {filePath}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void copyResolved()}
              disabled={!result}
              className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {copied ? t('common.copied') : t('repo.conflicts.copy')}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md bg-primary px-3 py-1 text-sm font-medium text-white hover:bg-primary-container"
            >
              {t('common.close')}
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <p className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              {t('repo.conflicts.resolving')}
            </p>
          ) : error ? (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
              {error}
            </p>
          ) : result ? (
            <>
              <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                {t('repo.conflicts.verifyHint')}
              </p>
              {result.truncated && (
                <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                  {t('repo.conflicts.truncated')}
                </p>
              )}
              <MarkdownView content={markdown} />
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
