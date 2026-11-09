import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { generateReleaseNotes, getTags } from '../api/client'
import type { ReleaseNotesResponse } from '../api/types'
import { useI18n } from '../i18n'
import MarkdownView from './MarkdownView'

interface ReleaseNotesModalProps {
  repositoryId: number
  onClose: () => void
}

export default function ReleaseNotesModal({
  repositoryId,
  onClose,
}: ReleaseNotesModalProps) {
  const { locale, t } = useI18n()
  const [tags, setTags] = useState<string[]>([])
  const [tagsLoading, setTagsLoading] = useState(true)
  const [fromTag, setFromTag] = useState('')
  const [toTag, setToTag] = useState('HEAD')
  const [notes, setNotes] = useState<ReleaseNotesResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let active = true
    void getTags(repositoryId)
      .then((data) => {
        if (!active) {
          return
        }
        setTags(data.tags)
        setFromTag((current) => current || data.tags[0] || '')
      })
      .catch(() => {
        if (active) {
          setTags([])
        }
      })
      .finally(() => {
        if (active) {
          setTagsLoading(false)
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

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const from = fromTag.trim()
    const to = toTag.trim() || 'HEAD'
    if (!from) {
      setError(t('repo.releaseNotes.fromRequired'))
      return
    }
    setLoading(true)
    setError(null)
    setNotes(null)
    try {
      setNotes(await generateReleaseNotes(repositoryId, from, to, locale))
    } catch {
      setError(t('repo.releaseNotes.error'))
    } finally {
      setLoading(false)
    }
  }

  async function copyNotes() {
    if (!notes) {
      return
    }
    try {
      await navigator.clipboard.writeText(notes.changelog)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setError(t('repo.releaseNotes.copyError'))
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t('repo.releaseNotes.title')}
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl dark:bg-slate-900"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t('repo.releaseNotes.title')}
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {t('repo.releaseNotes.hint')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void copyNotes()}
              disabled={!notes}
              className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {copied ? t('common.copied') : t('repo.releaseNotes.copy')}
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
          <form className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={handleGenerate}>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {t('repo.releaseNotes.fromTag')}
              <input
                list="release-notes-tags"
                value={fromTag}
                onChange={(event) => setFromTag(event.target.value)}
                placeholder="v1.0.0"
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {t('repo.releaseNotes.toTag')}
              <input
                list="release-notes-tags"
                value={toTag}
                onChange={(event) => setToTag(event.target.value)}
                placeholder="HEAD"
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>
            <button
              type="submit"
              disabled={loading || tagsLoading || !fromTag.trim()}
              className="self-end rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? t('repo.releaseNotes.generating') : t('repo.releaseNotes.generate')}
            </button>
            <datalist id="release-notes-tags">
              {tags.map((tag) => (
                <option key={tag} value={tag} />
              ))}
            </datalist>
          </form>

          {error && (
            <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
              {error}
            </p>
          )}

          {loading ? (
            <p className="mt-5 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              {t('repo.releaseNotes.generating')}
            </p>
          ) : notes ? (
            <div className="mt-5">
              {notes.cached && (
                <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                  {t('repo.releaseNotes.cached')}
                </p>
              )}
              {notes.truncated && (
                <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                  {t('repo.releaseNotes.truncated')}
                </p>
              )}
              <MarkdownView content={notes.changelog} />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
