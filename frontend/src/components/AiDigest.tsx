import { useState } from 'react'

import { getDashboardAdvice } from '../api/client'
import type { DashboardAdvice } from '../api/types'
import { useI18n } from '../i18n'
import MarkdownView from './MarkdownView'

export default function AiDigest() {
  const { locale, t } = useI18n()
  const [advice, setAdvice] = useState<DashboardAdvice | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function generate() {
    setLoading(true)
    setError(null)
    try {
      setAdvice(await getDashboardAdvice(locale))
    } catch {
      setError(t('dashboard.aiDigestError'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-primary/20 bg-white p-4 shadow-sm dark:border-primary/30 dark:bg-slate-900">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-primary dark:text-primary">
            {t('dashboard.aiDigestTitle')}
          </h2>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {t('dashboard.aiDigestHint')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {advice?.cached && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              {t('dashboard.aiDigestCached')}
            </span>
          )}
          <button
            type="button"
            onClick={() => void generate()}
            disabled={loading}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-container disabled:opacity-60"
          >
            {loading
              ? t('dashboard.aiDigestLoading')
              : t('dashboard.aiDigestGenerate')}
          </button>
        </div>
      </div>
      {loading ? (
        <p className="mt-3 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          {t('dashboard.aiDigestLoading')}
        </p>
      ) : error ? (
        <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
          {error}
        </p>
      ) : advice ? (
        <div className="mt-3">
          <MarkdownView content={advice.advice} />
        </div>
      ) : null}
    </div>
  )
}
