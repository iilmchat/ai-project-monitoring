import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { chatWithCode } from '../api/client'
import type { ChatMessage, CodeSearchResult } from '../api/types'
import { useI18n } from '../i18n'
import type { TranslationKey } from '../i18n'
import MarkdownView from './MarkdownView'

interface ChatEntry {
  role: 'user' | 'assistant'
  content: string
  citations?: CodeSearchResult[]
}

function errorMessage(cause: unknown, t: (key: TranslationKey) => string): string {
  const text = cause instanceof Error ? cause.message : ''
  if (text.includes('rag_unavailable')) {
    return t('search.unavailable')
  }
  if (text.includes('llm_unavailable')) {
    return t('search.chatLlmUnavailable')
  }
  return t('search.chatError')
}

export default function CodeChat() {
  const { t } = useI18n()
  const [messages, setMessages] = useState<ChatEntry[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = endRef.current
    if (element && typeof element.scrollIntoView === 'function') {
      element.scrollIntoView({ block: 'nearest' })
    }
  }, [messages, loading])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const query = input.trim()
    if (query.length < 3 || loading) {
      return
    }
    const history: ChatMessage[] = messages.map((message) => ({
      role: message.role,
      content: message.content,
    }))
    const next = [...messages, { role: 'user' as const, content: query }]
    setMessages(next)
    setInput('')
    setLoading(true)
    setError(null)
    try {
      const response = await chatWithCode({ query, history, limit: 5, min_score: 0.2 })
      setMessages([
        ...next,
        {
          role: 'assistant',
          content: response.answer,
          citations: response.citations,
        },
      ])
    } catch (cause) {
      setError(errorMessage(cause, t))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t('search.chatTitle')}
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {t('search.chatHint')}
          </p>
        </div>
        {messages.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setMessages([])
              setError(null)
            }}
            className="rounded-md border border-slate-300 px-3 py-1 text-xs dark:border-slate-600"
          >
            {t('search.chatClear')}
          </button>
        )}
      </div>

      <div className="max-h-[28rem] min-h-[12rem] space-y-3 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t('search.chatEmpty')}
          </p>
        ) : (
          messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                  message.role === 'user'
                    ? 'bg-primary text-white'
                    : 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100'
                }`}
              >
                {message.role === 'assistant' ? (
                  <MarkdownView content={message.content} />
                ) : (
                  <p className="whitespace-pre-wrap">{message.content}</p>
                )}
                {message.citations && message.citations.length > 0 && (
                  <ul className="mt-2 space-y-1 border-t border-slate-200 pt-2 text-xs dark:border-slate-700">
                    {message.citations.map((citation) => (
                      <li key={`${citation.repository_id}:${citation.path}:${citation.start_line}`}>
                        {citation.url ? (
                          <a
                            href={citation.url}
                            target="_blank"
                            rel="noreferrer"
                            className="font-mono text-primary underline-offset-2 hover:underline"
                          >
                            {citation.repository_name}/{citation.path}:{citation.start_line}
                          </a>
                        ) : (
                          <Link
                            to={`/repo/${citation.repository_id}`}
                            className="font-mono text-primary underline-offset-2 hover:underline"
                          >
                            {citation.repository_name}/{citation.path}:{citation.start_line}
                          </Link>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ))
        )}
        {loading && (
          <p className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            {t('search.chatThinking')}
          </p>
        )}
        <div ref={endRef} />
      </div>

      {error && (
        <p className="mx-4 mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
          {error}
        </p>
      )}

      <form
        onSubmit={(event) => void submit(event)}
        className="flex gap-2 border-t border-slate-200 p-4 dark:border-slate-700"
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={t('search.chatPlaceholder')}
          aria-label={t('search.chatPlaceholder')}
          className="min-w-0 flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        />
        <button
          type="submit"
          disabled={loading || input.trim().length < 3}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? t('search.chatSending') : t('search.chatSend')}
        </button>
      </form>
    </div>
  )
}
