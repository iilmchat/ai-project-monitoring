import { useEffect, useState } from 'react'

import { explainSast, getSast } from '../api/client'
import type { SastFinding, SastReport } from '../api/types'
import { useI18n } from '../i18n'
import RelativeTime from './ui/RelativeTime'

const SEVERITY_CLASS: Record<string, string> = {
  critical: 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-200',
  high: 'bg-orange-100 text-orange-800 dark:bg-orange-900/50 dark:text-orange-200',
  medium: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200',
  low: 'bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-200',
  unknown: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
}

export default function SastBlock({
  repositoryId,
  llmEnabled,
}: {
  repositoryId: number
  llmEnabled: boolean
}) {
  const { t } = useI18n()
  const [report, setReport] = useState<SastReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<SastFinding | null>(null)
  const [explanation, setExplanation] = useState('')
  const [explainLoading, setExplainLoading] = useState(false)
  const [explainError, setExplainError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    void getSast(repositoryId)
      .then((data) => {
        if (active) {
          setReport(data)
          setError(null)
        }
      })
      .catch(() => {
        if (active) setError(t('repo.sast.error'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [repositoryId, t])

  async function refresh() {
    setRefreshing(true)
    try {
      setReport(await getSast(repositoryId, true))
      setError(null)
    } catch {
      setError(t('repo.sast.error'))
    } finally {
      setRefreshing(false)
    }
  }

  async function explain(item: SastFinding) {
    setSelected(item)
    setExplanation('')
    setExplainError(null)
    setExplainLoading(true)
    try {
      const result = await explainSast(repositoryId, {
        rule_id: item.rule_id,
        message: item.message,
        file: item.file,
        line: item.line,
        snippet: item.snippet ?? '',
      })
      setExplanation(result.explanation)
    } catch {
      setExplainError(t('repo.errors.llmUnavailable'))
    } finally {
      setExplainLoading(false)
    }
  }

  return (
    <div
      data-testid="sast-block"
      className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {t('repo.sast.title')}
        </h2>
        <div className="flex items-center gap-2">
          {report && (
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-200">
              {t('repo.sast.total', { count: report.summary.total })}
            </span>
          )}
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={refreshing || loading}
            className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {refreshing ? t('repo.dependencies.checking') : t('common.refresh')}
          </button>
        </div>
      </div>
      <div className="space-y-3 p-4">
        {loading ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t('repo.sast.loading')}
          </p>
        ) : error ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
            {error}
          </p>
        ) : report === null ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t('repo.sast.noData')}
          </p>
        ) : (
          <>
            {report.status === 'unavailable' && (
              <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                {t('repo.sast.unavailable')}
              </p>
            )}
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {t('repo.sast.tools')}:{' '}
              {report.tools
                .map((tool) => `${tool.name} — ${tool.status}`)
                .join(', ')}
            </p>
            {report.findings.length > 0 ? (
              <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200 dark:divide-slate-700 dark:border-slate-700">
                {report.findings.map((item) => (
                  <li
                    key={item.fingerprint}
                    className="flex flex-wrap items-start justify-between gap-2 px-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="font-mono text-xs text-slate-500 dark:text-slate-400">
                        {item.file}:{item.line}
                      </p>
                      <p className="text-sm text-slate-800 dark:text-slate-200">
                        {item.message}
                      </p>
                      <p className="mt-1 flex flex-wrap gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                        <span className="font-mono">{item.rule_id}</span>
                        <span>{item.tool}</span>
                        {item.cwe && <span>{item.cwe}</span>}
                        {item.confidence && (
                          <span>
                            {t('repo.sast.confidence')}: {item.confidence}
                          </span>
                        )}
                      </p>
                      {item.snippet && (
                        <code className="mt-1 block max-w-xl overflow-x-auto rounded bg-slate-100 px-2 py-1 font-mono text-[11px] dark:bg-slate-800">
                          {item.snippet}
                        </code>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          SEVERITY_CLASS[item.severity]
                        }`}
                      >
                        {item.severity}
                      </span>
                      {llmEnabled && (
                        <button
                          type="button"
                          onClick={() => void explain(item)}
                          className="rounded-md border border-primary px-2 py-0.5 text-[11px] font-medium text-primary hover:bg-primary/10"
                        >
                          {t('repo.sast.fixWithAi')}
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-emerald-700 dark:text-emerald-300">
                {t('repo.sast.noFindings')}
              </p>
            )}
            {report.truncated && (
              <p className="text-xs text-amber-700 dark:text-amber-300">
                {t('repo.sast.truncated')}
              </p>
            )}
            <p className="text-xs text-slate-400 dark:text-slate-500">
              {t('repo.fields.checked')}:{' '}
              <RelativeTime date={report.checked_at} /> ·{' '}
              {t('repo.sast.footerMeta', {
                high: report.summary.high,
                medium: report.summary.medium,
                low: report.summary.low,
              })}
            </p>
          </>
        )}
      </div>

      {selected && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t('repo.sast.explanationTitle')}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setSelected(null)}
        >
          <div
            className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl dark:bg-slate-900"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold">
                  {t('repo.sast.explanationTitle')}
                </h3>
                <p className="mt-1 font-mono text-xs text-slate-500">
                  {selected.file}:{selected.line} · {selected.rule_id}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded-md border border-slate-300 px-3 py-1 text-sm dark:border-slate-600"
              >
                {t('common.close')}
              </button>
            </div>
            {explainLoading ? (
              <p className="mt-4 text-sm text-slate-500">
                {t('repo.sast.explanationLoading')}
              </p>
            ) : explainError ? (
              <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
                {explainError}
              </p>
            ) : (
              <p className="mt-4 whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-200">
                {explanation}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
