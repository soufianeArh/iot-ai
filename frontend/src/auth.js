// Holds the login session: the JWT plus who it belongs to. Kept in
// localStorage so a page refresh doesn't log someone out, api.js reads the
// token from here on every request.
import { computed, ref } from 'vue'

const STORAGE_KEY = 'mqai_session'

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

// A ref, not a plain variable: the topbar and the router guard both need to
// react the instant login or logout happens, not just on next reload.
export const session = ref(load())

export function setSession(data) {
  session.value = data
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)) } catch { /* private mode, session still works this tab */ }
}

// Merges fields into the live session (e.g. a renamed display name from the
// profile page) without needing a fresh login, the token itself is unchanged.
export function updateSessionFields(partial) {
  if (!session.value) return
  setSession({ ...session.value, ...partial })
}

export function clearSession() {
  session.value = null
  try { localStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ }
}

export function getToken() {
  return session.value?.token || null
}

// This is a UI convenience only, hiding a button someone can't use. The
// backend enforces the actual rule on every request regardless of what the
// frontend shows or hides.
export const canWrite = computed(() => {
  const role = session.value?.role
  return role === 'ADMIN' || role === 'OPERATOR'
})

export const isAdmin = computed(() => session.value?.role === 'ADMIN')
