/*
 * Four locales, English authoritative.
 *
 * A missing key falls back to English text, not the key name, so the app
 * works fine with just en.json while fr/ar/zh get filled in over time.
 *
 * Numbers stay Western digits in every locale, Arabic included
 * (numberingSystem: 'latn'), since this is a technical dashboard and
 * mixed numeral systems next to logs or API responses would just confuse.
 */
import { createI18n } from 'vue-i18n'

import en from './locales/en.json'
import fr from './locales/fr.json'
import ar from './locales/ar.json'
import zh from './locales/zh.json'

export const LOCALES = [
  { code: 'en', label: 'English', dir: 'ltr' },
  { code: 'fr', label: 'Français', dir: 'ltr' },
  { code: 'ar', label: 'العربية', dir: 'rtl' },
  { code: 'zh', label: '中文', dir: 'ltr' },
]

const STORAGE_KEY = 'mqai.locale'

function initialLocale() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && LOCALES.some((l) => l.code === saved)) return saved
  } catch { /* private mode, or storage blocked */ }

  const browser = (navigator.language || 'en').slice(0, 2)
  return LOCALES.some((l) => l.code === browser) ? browser : 'en'
}

const numberFormats = {}
for (const { code } of LOCALES) {
  numberFormats[code] = {
    // 'latn' on every locale, including ar - see the note above.
    plain: { numberingSystem: 'latn', maximumFractionDigits: 0 },
    decimal: { numberingSystem: 'latn', minimumFractionDigits: 2, maximumFractionDigits: 2 },
  }
}

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: 'en',
  // Suppressed: fr/ar/zh are still partial, and falling back to English is
  // expected, not a bug.
  missingWarn: false,
  fallbackWarn: false,
  messages: { en, fr, ar, zh },
  numberFormats,
})

/** Apply a locale to the document: translation, text direction and lang. */
export function setLocale(code) {
  const entry = LOCALES.find((l) => l.code === code) || LOCALES[0]
  i18n.global.locale.value = entry.code

  // This attribute is the only RTL switch needed; theme.css uses logical
  // properties throughout so nothing else has to change.
  document.documentElement.setAttribute('dir', entry.dir)
  document.documentElement.setAttribute('lang', entry.code)

  try { localStorage.setItem(STORAGE_KEY, entry.code) } catch { /* ignore */ }
}

export function currentDir() {
  const code = i18n.global.locale.value
  return (LOCALES.find((l) => l.code === code) || LOCALES[0]).dir
}
