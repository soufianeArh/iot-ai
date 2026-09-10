<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { session, updateSessionFields } from '../auth'
import { fmtTime } from '../usePoll'
import PasswordField from '../components/PasswordField.vue'

const { t, locale } = useI18n()

const displayName = ref(session.value?.displayName || '')
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

// role and createdAt aren't in the login response, only /me has them
const role = ref(session.value?.role || '')
const createdAt = ref('')

const busy = ref(false)
const error = ref('')
const success = ref('')

onMounted(async () => {
  try {
    const me = await api.me()
    role.value = me.role
    createdAt.value = me.createdAt
  } catch {
    // the form still works from the session's own fields either way
  }
})

async function onSubmit() {
  error.value = ''
  success.value = ''

  const body = {}
  if (displayName.value !== session.value?.displayName) body.displayName = displayName.value

  if (newPassword.value || currentPassword.value) {
    if (!currentPassword.value) { error.value = t('profile.currentPasswordRequired'); return }
    if (newPassword.value !== confirmPassword.value) { error.value = t('profile.passwordMismatch'); return }
    body.currentPassword = currentPassword.value
    body.newPassword = newPassword.value
  }

  if (!Object.keys(body).length) return

  busy.value = true
  try {
    const updated = await api.updateProfile(body)
    updateSessionFields({ displayName: updated.displayName })
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    success.value = t('profile.saved')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div>
    <h1>{{ t('profile.title') }}</h1>
    <p class="page-hint">{{ t('profile.hint') }}</p>

    <form class="card profile-card" @submit.prevent="onSubmit">
      <label class="field">
        <span>{{ t('auth.username') }}</span>
        <input :value="session?.username" class="ltr" disabled>
      </label>

      <label class="field">
        <span>{{ t('profile.displayName') }}</span>
        <input v-model="displayName" required>
      </label>

      <label class="field">
        <span>{{ t('profile.role') }}</span>
        <input :value="role" class="ltr" disabled>
      </label>

      <label class="field">
        <span>{{ t('profile.createdAt') }}</span>
        <input :value="fmtTime(createdAt, locale)" class="ltr" disabled>
      </label>

      <h2>{{ t('profile.changePassword') }}</h2>
      <p class="hint">{{ t('profile.changePasswordHint') }}</p>

      <PasswordField
        v-model="currentPassword"
        :label="t('profile.currentPassword')"
        autocomplete="current-password"
      />

      <PasswordField
        v-model="newPassword"
        :label="t('profile.newPassword')"
        autocomplete="new-password"
      />

      <PasswordField
        v-model="confirmPassword"
        :label="t('profile.confirmPassword')"
        autocomplete="new-password"
      />

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="success" class="success">{{ success }}</p>

      <button type="submit" :disabled="busy">{{ t('common.save') }}</button>
    </form>
  </div>
</template>

<style scoped>
.profile-card { max-width: 420px; }
.profile-card h2 { font-size: 1rem; margin: 1rem 0 .2rem; }
</style>
