import { useEffect, useState } from 'react'

import { getAuditLog } from '../api/client'
import type { AuditLogPage } from '../api/types'
import RelativeTime from '../components/ui/RelativeTime'
import { useI18n, useI18nNamespace } from '../i18n'

const PAGE_SIZE = 50

export default function AdminAudit() {
  const ready = useI18nNamespace('admin')
  const { t } = useI18n()
  const [page, setPage] = useState<AuditLogPage | null>(null)
  const [offset, setOffset] = useState(0)
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    void getAuditLog(PAGE_SIZE, offset)
      .then((data) => {
        if (active) {
          setPage(data)
          setError(null)
        }
      })
      .catch(() => {
        if (active) setError(t('admin.error'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [offset, reload, t])

  if (!ready) {
    return <p className="text-sm text-slate-500">{t('common.loading')}</p>
  }

  const items = page?.items ?? []
  const total = page?.total ?? 0
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + items.length, total)

  return (
    <section className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            {t('admin.auditTitle')}
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
            {t('admin.auditSubtitle')}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setReload((value) => value + 1)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600"
        >
          {t('admin.refresh')}
        </button>
      </header>

      {error && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-slate-500">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('admin.auditEmpty')}</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
              <tr>
                <th className="px-4 py-3">{t('admin.date')}</th>
                <th className="px-4 py-3">{t('admin.user')}</th>
                <th className="px-4 py-3">{t('admin.action')}</th>
                <th className="px-4 py-3">{t('admin.entity')}</th>
                <th className="px-4 py-3">{t('admin.details')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {items.map((entry) => (
                <tr key={entry.id}>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600 dark:text-slate-300">
                    <RelativeTime date={entry.created_at} />
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-800 dark:text-slate-200">
                    {entry.user.username ?? t('admin.system')}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                      {entry.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-600 dark:text-slate-300">
                    {entry.entity_type ?? '-'}
                    {entry.entity_id ? ` #${entry.entity_id}` : ''}
                  </td>
                  <td className="max-w-md px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
                    <code className="break-all">
                      {Object.keys(entry.details).length > 0
                        ? JSON.stringify(entry.details)
                        : '-'}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between gap-3 text-sm text-slate-600 dark:text-slate-300">
        <span>
          {t('admin.pageInfo', {
            from,
            to,
            total,
          })}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={offset === 0 || loading}
            onClick={() => setOffset(Math.max(offset - PAGE_SIZE, 0))}
            className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-50 dark:border-slate-600"
          >
            {t('admin.prev')}
          </button>
          <button
            type="button"
            disabled={offset + PAGE_SIZE >= total || loading}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-50 dark:border-slate-600"
          >
            {t('admin.next')}
          </button>
        </div>
      </div>
    </section>
  )
}
