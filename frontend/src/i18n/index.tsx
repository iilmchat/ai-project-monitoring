import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from 'react'
import type { ReactNode } from 'react'

import { common as enCommon } from './locales/en/common'
import { dashboard as enDashboard } from './locales/en/dashboard'
import { common as ruCommon } from './locales/ru/common'
import { dashboard as ruDashboard } from './locales/ru/dashboard'
import type { components as ruComponentsType } from './locales/ru/components'
import type { repository as ruRepositoryType } from './locales/ru/repository'
import type { settings as ruSettingsType } from './locales/ru/settings'

export type Locale = 'ru' | 'en'

/**
 * Namespaces that are loaded on demand when their page is opened. Keeping the
 * heavy dictionaries out of the entry chunk is what makes the initial bundle
 * small; everything else (header, dashboard, shared buttons) stays eager.
 */
export type I18nNamespace = 'settings' | 'repository' | 'components'

type Dictionary = Record<string, string>

const baseRu: Dictionary = {
  ...ruCommon,
  ...ruDashboard,
}

const baseEn: Dictionary = {
  ...enCommon,
  ...enDashboard,
}

export type TranslationKey =
  | keyof typeof ruCommon
  | keyof typeof ruDashboard
  | keyof typeof ruComponentsType
  | keyof typeof ruSettingsType
  | keyof typeof ruRepositoryType

type TranslationParams = Record<string, string | number>

interface I18nContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: TranslationKey, params?: TranslationParams) => string
  formatDate: (value: string | null | undefined) => string
  formatNumber: (value: number) => string
}

const STORAGE_KEY = 'iiruchating.locale'

const namespaceDictionaries: Record<I18nNamespace, Record<Locale, Dictionary>> = {
  settings: { ru: {}, en: {} },
  repository: { ru: {}, en: {} },
  components: { ru: {}, en: {} },
}

const namespaceReady: Record<I18nNamespace, boolean> = {
  settings: false,
  repository: false,
  components: false,
}

const namespaceRequests: Partial<Record<I18nNamespace, Promise<void>>> = {}

const namespaceListeners = new Set<() => void>()

function namespaceForKey(key: string): I18nNamespace | null {
  if (key.startsWith('settings.')) {
    return 'settings'
  }
  if (key.startsWith('repo.') || key.startsWith('OSV.')) {
    return 'repository'
  }
  if (
    key.startsWith('charts.') ||
    key.startsWith('global.') ||
    key.startsWith('heatmap.') ||
    key.startsWith('palette.') ||
    key.startsWith('readme.') ||
    key.startsWith('shortcuts.')
  ) {
    return 'components'
  }
  return null
}

function isI18nNamespaceReady(namespace: I18nNamespace): boolean {
  return namespaceReady[namespace]
}

function loadI18nNamespace(namespace: I18nNamespace): Promise<void> {
  if (namespaceReady[namespace]) {
    return Promise.resolve()
  }
  const existing = namespaceRequests[namespace]
  if (existing) {
    return existing
  }
  const request = (async () => {
    if (namespace === 'settings') {
      const [ruModule, enModule] = await Promise.all([
        import('./locales/ru/settings'),
        import('./locales/en/settings'),
      ])
      namespaceDictionaries.settings.ru = ruModule.settings
      namespaceDictionaries.settings.en = enModule.settings
    } else if (namespace === 'repository') {
      const [ruModule, enModule] = await Promise.all([
        import('./locales/ru/repository'),
        import('./locales/en/repository'),
      ])
      namespaceDictionaries.repository.ru = ruModule.repository
      namespaceDictionaries.repository.en = enModule.repository
    } else {
      const [ruModule, enModule] = await Promise.all([
        import('./locales/ru/components'),
        import('./locales/en/components'),
      ])
      namespaceDictionaries.components.ru = ruModule.components
      namespaceDictionaries.components.en = enModule.components
    }
    namespaceReady[namespace] = true
    for (const listener of namespaceListeners) {
      listener()
    }
  })()
  namespaceRequests[namespace] = request
  return request
}

/**
 * Loads the dictionary for a page and reports when it is safe to render.
 * Rendering is gated by the page component so that no translation key flashes
 * in the UI before the namespace chunk arrives.
 */
export function useI18nNamespace(namespace: I18nNamespace): boolean {
  const ready = useSyncExternalStore(
    subscribeToNamespaces,
    () => isI18nNamespaceReady(namespace),
    () => isI18nNamespaceReady(namespace),
  )

  useEffect(() => {
    if (!ready) {
      void loadI18nNamespace(namespace)
    }
  }, [namespace, ready])

  return ready
}

function subscribeToNamespaces(listener: () => void): () => void {
  namespaceListeners.add(listener)
  return () => {
    namespaceListeners.delete(listener)
  }
}

function resolve(locale: Locale, key: string): string {
  const base = locale === 'en' ? baseEn : baseRu
  const namespaced = namespaceForKey(key)
  if (namespaced !== null) {
    const dictionary = namespaceDictionaries[namespaced][locale]
    return dictionary[key] ?? namespaceDictionaries[namespaced].ru[key] ?? key
  }
  return base[key] ?? baseRu[key] ?? key
}

const fallbackContext: I18nContextValue = {
  locale: 'ru',
  setLocale: () => undefined,
  t: (key, params) => interpolate(resolve('ru', key), params),
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
    (key: TranslationKey, params?: TranslationParams): string =>
      interpolate(resolve(locale, key), params),
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
