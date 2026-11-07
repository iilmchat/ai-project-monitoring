import { useI18n } from '../i18n'

export default function LanguageToggle() {
  const { locale, setLocale, t } = useI18n()

  return (
    <div
      role="group"
      aria-label={t('common.language')}
      className="inline-flex overflow-hidden rounded-md border border-slate-300 text-xs font-semibold dark:border-slate-600"
    >
      {(['ru', 'en'] as const).map((value) => (
        <button
          key={value}
          type="button"
          onClick={() => setLocale(value)}
          aria-pressed={locale === value}
          title={value === 'ru' ? 'Русский' : 'English'}
          className={`px-2 py-1 transition ${
            locale === value
              ? 'bg-primary text-white'
              : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
          }`}
        >
          {value.toUpperCase()}
        </button>
      ))}
    </div>
  )
}
