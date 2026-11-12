import { lazy, Suspense, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

import {
  getCodeSearchStatus,
  indexCode,
  searchCode,
} from '../api/client'
import type {
  CodeIndexStatus,
  CodeSearchResponse,
  CodeSearchResult,
} from '../api/types'
import { useI18n, useI18nNamespace } from '../i18n'

const CodeChat = lazy(() => import('../components/CodeChat'))

const LANGUAGES = [
  'python',
  'typescript',
  'tsx',
  'javascript',
  'markdown',
] as const

export default function CodeSearchPage() {
  const { t } = useI18n()
  const dictionaryReady = useI18nNamespace('search')

  if (!dictionaryReady) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
  }

  return <CodeSearchContent />
}

function CodeSearchContent() {
  const { t } = useI18n()
  const [mode, setMode] = useState<'search' | 'chat'>('search')
  const [query, setQuery] = useState('')
  const [language, setLanguage] = useState('')
  const [status, setStatus] = useState<CodeIndexStatus | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [response, setResponse] = useState<CodeSearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [indexing, setIndexing] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ragUnavailable, setRagUnavailable] = useState(false)

  function describeError(cause: unknown): string {
    const text = cause instanceof Error ? cause.message : ''
    if (text.includes('rag_unavailable')) {
      return t('search.ragUnavailable')
    }
    if (text.includes('embedding_model_not_configured')) {
      return t('search.embeddingNotConfigured')
    }
    if (text.includes('dimension_mismatch')) {
      return t('search.embeddingDimensionMismatch')
    }
    if (
      text.includes('embedding_model_unavailable') ||
      text.includes('embedding_unavailable')
    ) {
      return t('search.embeddingUnavailable')
    }
    return t('search.error')
  }

  function isRagUnavailable(cause: unknown): boolean {
    return cause instanceof Error && cause.message.includes('rag_unavailable')
  }

  async function loadStatus() {
    try {
      setStatus(await getCodeSearchStatus())
      setStatusError(null)
      setRagUnavailable(false)
    } catch (cause) {
      setStatus(null)
      if (isRagUnavailable(cause)) {
        setRagUnavailable(true)
        setStatusError(null)
      } else {
        setStatusError(describeError(cause))
      }
    }
  }

  useEffect(() => {
    void loadStatus()
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (query.trim().length < 3) {
      return
    }
    setLoading(true)
    setError(null)
    setMessage(null)
    try {
      setResponse(
        await searchCode({
          query: query.trim(),
          limit: 5,
          min_score: 0.2,
          language: language || undefined,
        }),
      )
    } catch (cause) {
      setResponse(null)
      if (isRagUnavailable(cause)) {
        setRagUnavailable(true)
        setError(null)
      } else {
        setError(describeError(cause))
      }
    } finally {
      setLoading(false)
    }
  }

  async function startIndexing() {
    setIndexing(true)
    setError(null)
    setMessage(null)
    try {
      await indexCode({})
      setMessage(t('search.indexStarted'))
      for (let attempt = 0; attempt < 12; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 5000))
        try {
          const next = await getCodeSearchStatus()
          setStatus(next)
          setStatusError(null)
          if (!next.running) {
            break
          }
        } catch {
          break
        }
      }
    } catch (cause) {
      if (isRagUnavailable(cause)) {
        setRagUnavailable(true)
        setError(null)
      } else {
        setError(describeError(cause))
      }
    } finally {
      setIndexing(false)
    }
  }

  async function copyPath(path: string) {
    try {
      await navigator.clipboard.writeText(path)
      setMessage(t('search.copied'))
    } catch {
      setError(t('search.error'))
    }
  }

  const indexed = (status?.indexed_chunks ?? 0) > 0

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('search.title')}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t('search.subtitle')}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5 text-sm dark:border-slate-600 dark:bg-slate-900">
          <button
            type="button"
            onClick={() => setMode('search')}
            className={`rounded-md px-3 py-1.5 font-medium ${
              mode === 'search'
                ? 'bg-primary text-white'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
            }`}
          >
            {t('search.modeSearch')}
          </button>
          <button
            type="button"
            onClick={() => setMode('chat')}
            className={`rounded-md px-3 py-1.5 font-medium ${
              mode === 'chat'
                ? 'bg-primary text-white'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
            }`}
          >
            {t('search.modeChat')}
          </button>
        </div>
      </div>

      {ragUnavailable && (
        <div
          role="status"
          className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800 dark:border-sky-800 dark:bg-sky-900/30 dark:text-sky-200"
        >
          {t('search.ragUnavailable')}
        </div>
      )}

      {mode === 'chat' && (
        <Suspense fallback={<p className="text-sm text-slate-500">{t('common.loading')}</p>}>
          <CodeChat />
        </Suspense>
      )}

      {mode === 'search' && (
      <form
        onSubmit={(event) => void submit(event)}
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="flex flex-col gap-3 md:flex-row">
          <label className="min-w-0 flex-1">
            <span className="sr-only">{t('search.placeholder')}</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('search.placeholder')}
              aria-label={t('search.placeholder')}
              className="block w-full rounded-lg border border-slate-300 px-4 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
            <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">
              {t('search.queryHint')}
            </span>
          </label>
          <label className="text-sm text-slate-600 dark:text-slate-300">
            <span className="sr-only">{t('search.language')}</span>
            <select
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
              aria-label={t('search.language')}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            >
              <option value="">{t('search.languageAll')}</option>
              {LANGUAGES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={loading || ragUnavailable || query.trim().length < 3}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? t('search.searching') : t('search.submit')}
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
          {statusError ? (
            <span>{statusError}</span>
          ) : status ? (
            <span>
              {t('search.status', {
                chunks: status.indexed_chunks,
                repos: status.indexed_repositories,
              })}
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => void loadStatus()}
            className="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-600"
          >
            {t('search.refreshStatus')}
          </button>
          <button
            type="button"
            onClick={() => void startIndexing()}
            disabled={indexing || ragUnavailable || status?.running}
            className="rounded-md border border-primary px-2 py-1 text-xs font-medium text-primary disabled:opacity-60"
          >
            {indexing || status?.running ? t('search.indexing') : t('search.index')}
          </button>
        </div>

        {!statusError && !indexed && (
          <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
            {t('search.noIndex')}
          </p>
        )}
        {message && (
          <p className="mt-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200">
            {message}
          </p>
        )}
        {error && (
          <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
            {error}
          </p>
        )}
      </form>
      )}

      {mode === 'search' && (
      <div aria-live="polite">
        {response && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">
                {t('search.results')} · {response.results.length}
              </h2>
              {response.stale && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
                  {t('search.stale')}
                </span>
              )}
            </div>
            {response.results.length === 0 ? (
              <p className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                {t('search.empty')}
              </p>
            ) : (
              <ul className="space-y-3">
                {response.results.map((result) => (
                  <ResultCard
                    key={`${result.repository_id}:${result.path}:${result.start_line}`}
                    result={result}
                    onCopy={() => void copyPath(result.path)}
                  />
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
      )}
    </section>
  )
}

function ResultCard({
  result,
  onCopy,
}: {
  result: CodeSearchResult
  onCopy: () => void
}) {
  const { t } = useI18n()
  return (
    <li className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-mono text-sm font-medium text-slate-900 dark:text-slate-100">
            {result.path}
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {result.repository_name} ·{' '}
            {t('search.lines', {
              start: result.start_line,
              end: result.end_line,
            })}{' '}
            · {t('search.score', { score: result.score.toFixed(2) })}
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {result.language}
        </span>
      </div>
      <pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">
        <code>{result.snippet}</code>
      </pre>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <button
          type="button"
          onClick={onCopy}
          className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-600"
        >
          {t('search.copyPath')}
        </button>
        <Link
          to={`/repo/${result.repository_id}`}
          className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-600"
        >
          {t('search.openProject')}
        </Link>
        {result.url && (
          <a
            href={result.url}
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-600"
          >
            {t('search.openGithub')}
          </a>
        )}
      </div>
    </li>
  )
}
