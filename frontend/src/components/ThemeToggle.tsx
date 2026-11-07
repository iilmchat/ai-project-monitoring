import { useI18n } from '../i18n'
import { useTheme } from '../theme/ThemeContext'

export default function ThemeToggle() {
  const { t } = useI18n()
  const { resolved, toggle } = useTheme()
  const isDark = resolved === 'dark'
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={t('common.theme')}
      title={isDark ? t('common.themeLight') : t('common.themeDark')}
      className="rounded-md border border-slate-300 px-2.5 py-1 text-sm text-slate-700 transition hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
    >
      {isDark ? '☀' : '🌙'}
    </button>
  )
}
