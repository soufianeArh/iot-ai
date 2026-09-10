<script setup>
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
  <header class="topbar">
    <div class="brand">
      {{ t('app.name') }}<small>{{ t('app.tagline') }}</small>
    </div>

    <nav v-if="route.path !== '/login'">
      <RouterLink to="/devices">{{ t('nav.devices') }}</RouterLink>
      <RouterLink to="/cameras">{{ t('nav.cameras') }}</RouterLink>
      <RouterLink to="/detections">{{ t('nav.detections') }}</RouterLink>
      <RouterLink to="/alerts">{{ t('nav.alerts') }}</RouterLink>
      <RouterLink to="/ask">{{ t('nav.ask') }}</RouterLink>
      <RouterLink v-if="isAdmin" to="/users">{{ t('nav.users') }}</RouterLink>
    </nav>

    <!-- margin-inline-start:auto keeps this at the trailing edge either way. -->
    <div class="spacer"></div>

    <div v-if="session" class="row user-box">
      <RouterLink to="/profile" class="user-name">{{ session.displayName }}</RouterLink>
      <span class="pill role-badge">{{ roleLabel(session.role) }}</span>
      <button class="ghost" type="button" @click="onLogout">{{ t('auth.signOut') }}</button>
    </div>

    <label class="lang">
      <span class="visually-hidden">{{ t('app.language') }}</span>
      <select :value="locale" @change="onLocaleChange">
        <option v-for="l in LOCALES" :key="l.code" :value="l.code">{{ l.label }}</option>
      </select>
    </label>
  </header>

  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.lang select {
  width: auto;
  background: rgba(255, 255, 255, .12);
  color: #fff;
  border-color: rgba(255, 255, 255, .25);
}
.lang select option { color: #16202c; }

.user-box { color: #cfe0f5; font-size: .85rem; }
.user-name { color: #fff; text-decoration: none; }
.user-name:hover { text-decoration: underline; }
.user-box .ghost {
  border-color: rgba(255, 255, 255, .35);
  color: #fff;
  padding: .3rem .6rem;
}
.user-box .ghost:hover { background: rgba(255, 255, 255, .12); }

/* .pill's default colours assume a light card background, not this dark
   topbar, same reasoning as .lang select and .user-box .ghost above. */
.role-badge { background: rgba(255, 255, 255, .16); color: #fff; }

.visually-hidden {
  position: absolute;
  width: 1px; height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
