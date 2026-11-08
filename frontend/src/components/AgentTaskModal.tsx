import { useEffect, useState } from 'react'

import { generateAgentTask } from '../api/client'
import type { AgentTask } from '../api/types'
import { useI18n } from '../i18n'
import MarkdownView from './MarkdownView'

interface AgentTaskModalProps {
  repositoryId: number
  onClose: () => void
}

export default function AgentTaskModal({
  repositoryId,
  onClose,
}: AgentTaskModalProps) {
  const { locale, t } = useI18n()
  const [task, setTask] = useState<AgentTask | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let active = true
    void generateAgentTask(repositoryId, locale)
      .then((result) => {
        if (active) {
          setTask(result)
          setError(null)
        }
      })
      .catch(() => {
        if (active) {
          setError(t('repo.agentTask.error'))
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
  }, [locale, repositoryId, t])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  async function copyTask() {
    if (!task) {
      return
    }
    try {
      await navigator.clipboard.writeText(task.task)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setError(t('repo.agentTask.copyError'))
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t('repo.agentTask.title')}
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl dark:bg-slate-900"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t('repo.agentTask.title')}
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {t('repo.agentTask.hint')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void copyTask()}
              disabled={!task}
              className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {copied ? t('common.copied') : t('repo.agentTask.copy')}
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
              {t('repo.agentTask.loading')}
            </p>
          ) : error ? (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
              {error}
            </p>
          ) : task ? (
            <MarkdownView content={task.task} />
          ) : null}
        </div>
      </div>
    </div>
  )
}
