import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { useI18n, useI18nNamespace } from '../i18n'
import { useAuthStore } from '../store/useAuthStore'

export default function LoginPage() {
  const { t } = useI18n()
  const dictionaryReady = useI18nNamespace('auth')

  if (!dictionaryReady) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
  }

  return <LoginForm />
}

function LoginForm() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user, login, error, clearError } = useAuthStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const nextParam = searchParams.get('next')
  const target = nextParam?.startsWith('/') ? nextParam : '/'

  useEffect(() => {
    if (user) {
      navigate(target, { replace: true })
    }
  }, [navigate, target, user])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!username.trim() || !password) {
      return
    }
    setSubmitting(true)
    const ok = await login(username.trim(), password)
    setSubmitting(false)
    if (ok) {
      navigate(target, { replace: true })
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <form
        onSubmit={(event) => void submit(event)}
        className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <h1 className="text-2xl font-semibold tracking-tight">{t('auth.title')}</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {t('auth.subtitle')}
        </p>

        <div className="mt-5 space-y-3">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            {t('auth.username')}
            <input
              required
              autoComplete="username"
              value={username}
              onChange={(event) => {
                setUsername(event.target.value)
                clearError()
              }}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            {t('auth.password')}
            <input
              required
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value)
                clearError()
              }}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>
        </div>

        {error && (
          <p
            role="alert"
            className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200"
          >
            {error === 'too_many_attempts'
              ? t('auth.rateLimited')
              : t('auth.invalid')}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting || !username.trim() || !password}
          className="mt-5 w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? t('auth.submitting') : t('auth.submit')}
        </button>
      </form>
    </div>
  )
}
