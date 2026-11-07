import { useEffect, useState } from 'react'

import { getReadme, getRepositoryDoc } from '../api/client'
import { useI18n } from '../i18n'
import { resolveDocumentPath } from '../utils/markdownLinks'
import MarkdownView from './MarkdownView'

interface ReadmeModalProps {
  repositoryId: number
  onClose: () => void
}

interface DocumentState {
  path: string
  content: string
}

export default function ReadmeModal({ repositoryId, onClose }: ReadmeModalProps) {
  const { t } = useI18n()
  const [history, setHistory] = useState<DocumentState[]>([])
  const [index, setIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void getReadme(repositoryId)
      .then((readme) => {
        if (active) {
          setHistory([{ path: readme.path, content: readme.content }])
          setIndex(0)
          setError(null)
        }
      })
      .catch(() => {
        if (active) {
          setError(t('readme.notFound'))
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
  }, [repositoryId])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const current = history[index] ?? null

  async function openInternalLink(href: string) {
    if (!current) {
      return
    }
    const nextPath = resolveDocumentPath(current.path, href)
    if (!nextPath) {
      return
    }
    setLoading(true)
    try {
      const document = await getRepositoryDoc(repositoryId, nextPath)
      setHistory((items) => [...items.slice(0, index + 1), document])
      setIndex((value) => value + 1)
      setError(null)
    } catch {
      setError(t('readme.openError', { path: nextPath }))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="README проекта"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl dark:bg-slate-900"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t('readme.title')}
            </h2>
            <p className="truncate font-mono text-xs text-slate-500 dark:text-slate-400">
              {current?.path ?? 'README'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIndex((value) => Math.max(value - 1, 0))}
              disabled={index === 0}
              className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              ← {t('common.back')}
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
            <p className="text-sm text-slate-500 dark:text-slate-400">{t('readme.loading')}</p>
          ) : error ? (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
              {error}
            </p>
          ) : current ? (
            <MarkdownView content={current.content} onOpenLink={(href) => void openInternalLink(href)} />
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">{t('readme.empty')}</p>
          )}
        </div>
      </div>
    </div>
  )
}
