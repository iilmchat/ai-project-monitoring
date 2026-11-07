import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { common as enCommon } from './locales/en/common'
import { components as enComponents } from './locales/en/components'
import { dashboard as enDashboard } from './locales/en/dashboard'
import { repository as enRepository } from './locales/en/repository'
import { settings as enSettings } from './locales/en/settings'
import { common as ruCommon } from './locales/ru/common'
import { components as ruComponents } from './locales/ru/components'
import { dashboard as ruDashboard } from './locales/ru/dashboard'
import { repository as ruRepository } from './locales/ru/repository'
import { settings as ruSettings } from './locales/ru/settings'

export type Locale = 'ru' | 'en'

const ru = {
  ...ruCommon,
  ...ruDashboard,
  ...ruSettings,
  ...ruComponents,
  ...ruRepository,
}

export type TranslationKey = keyof typeof ru

const en: Record<TranslationKey, string> = {
  ...enCommon,
  ...enDashboard,
  ...enSettings,
  ...enComponents,
  ...enRepository,
}

type TranslationParams = Record<string, string | number>

interface I18nContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: TranslationKey, params?: TranslationParams) => string
  formatDate: (value: string | null | undefined) => string
  formatNumber: (value: number) => string
}

const STORAGE_KEY = 'iiruchating.locale'

const fallbackContext: I18nContextValue = {
  locale: 'ru',
  setLocale: () => undefined,
  t: (key, params) => interpolate(ru[key] ?? key, params),
  formatDate: (value) => {
    if (!value) {
      return '—'
    }
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('ru-RU')
  },
  formatNumber: (value) => new Intl.NumberFormat('ru-RU').format(value),
}

const I18nContext = createContext<I18nContextValue>(fallbackContext)

function detectLocale(): Locale {
  if (typeof window === 'undefined') {
    return 'ru'
  }
  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (stored === 'ru' || stored === 'en') {
    return stored
  }
  return window.navigator.language.toLowerCase().startsWith('ru') ? 'ru' : 'en'
}

function interpolate(template: string, params?: TranslationParams): string {
  if (!params) {
    return template
  }
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in params ? String(params[key]) : match,
  )
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(detectLocale)

  useEffect(() => {
    document.documentElement.lang = locale
    window.localStorage.setItem(STORAGE_KEY, locale)
  }, [locale])

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next)
  }, [])

  const t = useCallback(
    (key: TranslationKey, params?: TranslationParams): string => {
      const dictionary = locale === 'en' ? en : ru
      return interpolate(dictionary[key] ?? ru[key] ?? key, params)
    },
    [locale],
  )

  const formatDate = useCallback(
    (value: string | null | undefined): string => {
      if (!value) {
        return '—'
      }
      const parsed = new Date(value)
      if (Number.isNaN(parsed.getTime())) {
        return value
      }
      return parsed.toLocaleString(locale === 'ru' ? 'ru-RU' : 'en-US')
    },
    [locale],
  )

  const formatNumber = useCallback(
    (value: number): string =>
      new Intl.NumberFormat(locale === 'ru' ? 'ru-RU' : 'en-US').format(value),
    [locale],
  )

  const value = useMemo<I18nContextValue>(
    () => ({ locale, setLocale, t, formatDate, formatNumber }),
    [locale, setLocale, t, formatDate, formatNumber],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  return useContext(I18nContext)
}

export function statusLabel(
  key: string | null | undefined,
  t: (key: TranslationKey) => string,
): string {
  const normalized = key ?? 'unknown'
  return t(`status.${normalized}` as TranslationKey)
}

export function mirrorLabel(
  key: string | null | undefined,
  t: (key: TranslationKey) => string,
): string {
  const normalized = key ?? 'unavailable'
  return t(`mirror.${normalized}` as TranslationKey)
}

export function ciLabel(
  key: string | null | undefined,
  t: (key: TranslationKey) => string,
): string {
  const normalized = key ?? 'unknown'
  return t(`ci.${normalized}` as TranslationKey)
}
