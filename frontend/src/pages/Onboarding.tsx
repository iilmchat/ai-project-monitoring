import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { scan, updateSettings } from '../api/client'
import { isTauri, pickDirectory } from '../desktop/tauri'
import { useI18n } from '../i18n'

type Step = 1 | 2 | 3

const STEP_KEYS = {
  1: 'onboarding.welcomeTitle',
  2: 'onboarding.folderTitle',
  3: 'onboarding.tokensTitle',
} as const

export default function Onboarding() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>(1)
  const [scanRoot, setScanRoot] = useState('')
  const [githubToken, setGithubToken] = useState('')
  const [gitflicToken, setGitflicToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [picking, setPicking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const desktop = isTauri()

  async function handlePickDirectory() {
    setPicking(true)
    setError(null)
    try {
      const selected = await pickDirectory()
      if (selected) {
        setScanRoot(selected)
      }
    } catch {
      setError(t('onboarding.pickError'))
    } finally {
      setPicking(false)
    }
  }

  async function finish(skipTokens: boolean) {
    const roots = scanRoot.trim()
    if (!roots) {
      setError(t('onboarding.folderRequired'))
      setStep(2)
      return
    }

    setSaving(true)
    setError(null)
    try {
      const payload: {
        scan_roots: string
        github_token?: string
        gitflic_token?: string
      } = { scan_roots: roots }
      if (!skipTokens) {
        if (githubToken.trim()) payload.github_token = githubToken.trim()
        if (gitflicToken.trim()) payload.gitflic_token = gitflicToken.trim()
      }

      await updateSettings(payload)
      await scan()
      navigate('/', { replace: true })
    } catch {
      setError(t('onboarding.saveError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 px-4 py-10 dark:from-slate-950 dark:to-slate-900">
      <section className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-8 shadow-lg dark:border-slate-700 dark:bg-slate-900">
        <header className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary">
            IIRuchating · {t('onboarding.badge')}
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
            {t(STEP_KEYS[step])}
          </h1>
          <div
            className="mt-4 flex gap-2"
            aria-label={t('onboarding.progress')}
          >
            {([1, 2, 3] as Step[]).map((value) => (
              <span
                key={value}
                className={`h-1.5 flex-1 rounded-full ${
                  value <= step
                    ? 'bg-primary'
                    : 'bg-slate-200 dark:bg-slate-700'
                }`}
              />
            ))}
          </div>
        </header>

        {error && (
          <div
            role="alert"
            className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/40 dark:text-red-300"
          >
            {error}
          </div>
        )}

        {step === 1 && (
          <div className="space-y-5">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {t('onboarding.welcomeBody')}
            </p>
            <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
              <li>• {t('onboarding.bulletFolder')}</li>
              <li>• {t('onboarding.bulletTokens')}</li>
              <li>• {t('onboarding.bulletScan')}</li>
            </ul>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-container"
              >
                {t('onboarding.start')}
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {t('onboarding.folderBody')}
            </p>

            {desktop ? (
              <div className="space-y-3">
                <button
                  type="button"
                  onClick={() => void handlePickDirectory()}
                  disabled={picking}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  {picking
                    ? t('onboarding.pickingFolder')
                    : t('onboarding.pickFolder')}
                </button>
                <p className="break-all font-mono text-sm text-slate-700 dark:text-slate-300">
                  {scanRoot || t('onboarding.noFolder')}
                </p>
              </div>
            ) : (
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('onboarding.folderPath')}
                <input
                  value={scanRoot}
                  onChange={(event) => setScanRoot(event.target.value)}
                  placeholder={t('onboarding.folderPlaceholder')}
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
            )}

            <div className="flex justify-between">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {t('common.back')}
              </button>
              <button
                type="button"
                onClick={() => setStep(3)}
                disabled={!scanRoot.trim()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
              >
                {t('onboarding.next')}
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-5">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {t('onboarding.tokensBody')}
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('onboarding.githubToken')}
                <input
                  type="password"
                  value={githubToken}
                  onChange={(event) => setGithubToken(event.target.value)}
                  placeholder="ghp_…"
                  autoComplete="off"
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('onboarding.gitflicToken')}
                <input
                  type="password"
                  value={gitflicToken}
                  onChange={(event) => setGitflicToken(event.target.value)}
                  placeholder="glpat-…"
                  autoComplete="off"
                  className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
            </div>
            <div className="flex flex-wrap justify-between gap-2">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {t('common.back')}
              </button>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void finish(true)}
                  disabled={saving}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  {t('onboarding.skip')}
                </button>
                <button
                  type="button"
                  onClick={() => void finish(false)}
                  disabled={saving}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving ? t('common.saving') : t('onboarding.finish')}
                </button>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
