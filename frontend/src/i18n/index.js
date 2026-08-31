/*
 * Four locales, English authoritative.
 *
 * Two decisions worth knowing:
 *
 * FALLBACK IS ENGLISH, ALWAYS. A missing key renders the English string
 * rather than the key name, so the app is fully usable with en.json alone and
 * fr/ar/zh can be filled in at any pace without ever showing `alerts.title`
 * to a user.
 *
 * NUMBERS ARE WESTERN IN EVERY LOCALE, Arabic included. `numberingSystem:
 * 'latn'` forces 123 rather than ١٢٣. This is a technical dashboard - counts,
 * confidences and camera ids are compared against logs and API responses, and
 * mixing numeral systems between the two is a real source of confusion.
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
  // The console fills with warnings while fr/ar/zh are still stubs, and the
  // fallback is the intended behaviour, not a bug worth reporting.
  missingWarn: false,
  fallbackWarn: false,
  messages: { en, fr, ar, zh },
  numberFormats,
})

/** Apply a locale to the document: translation, text direction and lang. */
export function setLocale(code) {
  const entry = LOCALES.find((l) => l.code === code) || LOCALES[0]
  i18n.global.locale.value = entry.code

  // The whole of RTL support is this one attribute. It works only because the
  // stylesheet uses logical properties throughout - see styles/theme.css.
  document.documentElement.setAttribute('dir', entry.dir)
  document.documentElement.setAttribute('lang', entry.code)

  try { localStorage.setItem(STORAGE_KEY, entry.code) } catch { /* ignore */ }
}

export function currentDir() {
  const code = i18n.global.locale.value
  return (LOCALES.find((l) => l.code === code) || LOCALES[0]).dir
}
