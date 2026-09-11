<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { LOCALES, setLocale } from './i18n'
import { session, clearSession, isAdmin } from './auth'
import { api } from './api'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()

function onLocaleChange(event) {
  setLocale(event.target.value)
}

// Reuses the same role labels as the Users admin page, so the wording never
// drifts between the two places a role gets shown.
const roleLabels = { ADMIN: 'users.roleAdmin', OPERATOR: 'users.roleOperator', VIEWER: 'users.roleViewer' }
function roleLabel(role) {
  return roleLabels[role] ? t(roleLabels[role]) : role
}

// Remembered per browser, same convention as the locale choice
// (mqai.locale), so it's still hidden or shown the way it was left after a
// reload, not reset to open every time.
const SIDEBAR_KEY = 'mqai.sidebarOpen'
const sidebarOpen = ref(localStorage.getItem(SIDEBAR_KEY) !== 'false')
function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
  try { localStorage.setItem(SIDEBAR_KEY, String(sidebarOpen.value)) } catch { /* private mode, still works this tab */ }
}

async function onLogout() {
  // The token is stateless, this call has nothing to actually revoke server
  // side yet, so a failure here (e.g. token already expired) isn't worth
  // blocking the local logout on.
  try { await api.logout() } catch { /* already logged out either way */ }
  clearSession()
  router.replace('/login')
}
</script>

<template>
  <div class="app-shell">
    <aside v-if="route.path !== '/login' && sidebarOpen" class="sidebar">
      <div class="brand-row">
        <div class="brand">
          {{ t('app.name') }}<small>{{ t('app.tagline') }}</small>
        </div>
        <button class="sidebar-toggle" type="button" @click="toggleSidebar"
                :aria-label="t('app.hideSidebar')" :title="t('app.hideSidebar')">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="6" x2="21" y2="6"/>
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
      </div>

      <nav class="side-nav">
        <RouterLink to="/dashboard">{{ t('nav.dashboard') }}</RouterLink>
        <RouterLink to="/devices">{{ t('nav.devices') }}</RouterLink>
        <RouterLink v-if="isAdmin" to="/zones">{{ t('nav.zones') }}</RouterLink>
        <RouterLink to="/cameras">{{ t('nav.cameras') }}</RouterLink>
        <RouterLink to="/detections">{{ t('nav.detections') }}</RouterLink>
        <RouterLink to="/alerts">{{ t('nav.alerts') }}</RouterLink>
        <RouterLink to="/ask">{{ t('nav.ask') }}</RouterLink>
        <RouterLink v-if="isAdmin" to="/users">{{ t('nav.users') }}</RouterLink>
        <RouterLink v-if="isAdmin" to="/logs">{{ t('nav.logs') }}</RouterLink>
      </nav>

      <div class="sidebar-spacer"></div>

      <div v-if="session" class="user-box">
        <RouterLink to="/profile" class="profile-chip" :title="t('profile.title')">
          <svg class="user-icon" viewBox="0 0 24 24" width="15" height="15" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="8" r="4"/>
            <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"/>
          </svg>
          <span class="user-name">{{ session.displayName }}</span>
          <span class="pill role-badge">{{ roleLabel(session.role) }}</span>
        </RouterLink>
        <button class="ghost" type="button" @click="onLogout">{{ t('auth.signOut') }}</button>
      </div>

      <label class="lang">
        <span class="visually-hidden">{{ t('app.language') }}</span>
        <select :value="locale" @change="onLocaleChange">
          <option v-for="l in LOCALES" :key="l.code" :value="l.code">{{ l.label }}</option>
        </select>
      </label>
    </aside>

    <!-- Fixed, not part of the sidebar: it has to still be reachable once
         the sidebar itself is gone. -->
    <button v-if="route.path !== '/login' && !sidebarOpen" class="sidebar-reopen" type="button"
            @click="toggleSidebar" :aria-label="t('app.showSidebar')" :title="t('app.showSidebar')">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="6" x2="21" y2="6"/>
        <line x1="3" y1="12" x2="21" y2="12"/>
        <line x1="3" y1="18" x2="21" y2="18"/>
      </svg>
    </button>

    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.brand-row { display: flex; align-items: center; justify-content: space-between; padding-inline-end: .6rem; }

.sidebar-toggle, .sidebar-reopen {
  background: transparent;
  border: none;
  color: #cfe0f5;
  padding: .3rem;
  display: flex;
  cursor: pointer;
}
.sidebar-toggle:hover, .sidebar-reopen:hover { color: #fff; }

.sidebar-reopen {
  position: fixed;
  top: .6rem;
  inset-inline-start: .6rem;
  z-index: 20;
  background: var(--brand-900);
  border-radius: var(--radius);
  padding: .5rem;
}
.sidebar-reopen:hover { background: var(--brand-700); }

.lang select {
  width: auto;
  background: rgba(255, 255, 255, .12);
  color: #fff;
  border-color: rgba(255, 255, 255, .25);
  margin: 0 var(--gap);
}
.lang select option { color: #16202c; }

.user-box {
  color: #cfe0f5;
  font-size: .85rem;
  padding: 0 var(--gap);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: .4rem;
}

/* The name opens the profile page, so it needs to read as a control, not
   just text. Same bordered, hover-lit treatment as the Sign out button
   below it, plus a person icon. */
.profile-chip {
  display: flex;
  align-items: center;
  gap: .4rem;
  max-width: 100%;
  padding: .35rem .55rem;
  border: 1px solid rgba(255, 255, 255, .22);
  border-radius: var(--radius);
  color: #fff;
  text-decoration: none;
}
.profile-chip:hover {
  background: rgba(255, 255, 255, .12);
  border-color: rgba(255, 255, 255, .4);
}
.profile-chip .user-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.user-icon { flex-shrink: 0; opacity: .85; }

.user-box .ghost {
  border-color: rgba(255, 255, 255, .35);
  color: #fff;
  padding: .3rem .6rem;
}
.user-box .ghost:hover { background: rgba(255, 255, 255, .12); }

/* .pill's default colours assume a light card background, not this dark
   sidebar, same reasoning as .lang select and .user-box .ghost above. */
.role-badge { background: rgba(255, 255, 255, .16); color: #fff; }

.visually-hidden {
  position: absolute;
  width: 1px; height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
