import { useEffect, useMemo, useState } from 'react'

import { getHeatmap } from '../api/client'
import { useI18n } from '../i18n'

const CELL_STYLES = [
  'bg-slate-100 dark:bg-slate-800',
  'bg-emerald-200 dark:bg-emerald-900/60',
  'bg-emerald-300 dark:bg-emerald-700',
  'bg-emerald-500 dark:bg-emerald-500',
  'bg-emerald-700 dark:bg-emerald-300',
]

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10)
}

export default function Heatmap({ days = 365 }: { days?: number }) {
  const { t } = useI18n()
  const [data, setData] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    void getHeatmap(days)
      .then((values) => {
        if (active) setData(values)
      })
      .catch(() => {
        if (active) setData({})
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [days])

  const cells = useMemo(() => {
    const today = new Date()
    const result: { date: string; count: number; level: number }[] = []
    for (let offset = days - 1; offset >= 0; offset -= 1) {
      const date = new Date(today)
      date.setDate(today.getDate() - offset)
      const key = isoDate(date)
      const count = data[key] ?? 0
      const level = count === 0 ? 0 : Math.min(4, 1 + Math.floor(Math.log2(count)))
      result.push({ date: key, count, level })
    }
    return result
  }, [data, days])

  const total = useMemo(
    () => Object.values(data).reduce((sum, value) => sum + value, 0),
    [data],
  )

  return (
    <div
      data-testid="heatmap"
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {t('heatmap.title')}
        </h2>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {loading
            ? t('heatmap.loading')
            : t('heatmap.summary', { count: total, days })}
        </span>
      </div>
      <div className="mt-3 overflow-x-auto">
        <div className="grid grid-flow-col grid-rows-7 gap-1">
          {cells.map((cell) => (
            <div
              key={cell.date}
              title={`${cell.date}: ${cell.count}`}
              className={`h-3 w-3 rounded-sm ${CELL_STYLES[cell.level]}`}
            />
          ))}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-end gap-1 text-[10px] text-slate-400 dark:text-slate-500">
        <span>{t('heatmap.less')}</span>
        {CELL_STYLES.map((style, index) => (
          <span key={index} className={`h-2.5 w-2.5 rounded-sm ${style}`} />
        ))}
        <span>{t('heatmap.more')}</span>
      </div>
    </div>
  )
}
