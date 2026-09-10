<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { setSession } from '../auth'
import PasswordField from '../components/PasswordField.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

async function onSubmit() {
  busy.value = true
  error.value = ''
  try {
    const data = await api.login(username.value, password.value)
    setSession(data)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/devices'
    router.replace(redirect)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <form class="card login-card" @submit.prevent="onSubmit">
      <h1>{{ t('app.name') }}</h1>
      <p class="page-hint">{{ t('auth.subtitle') }}</p>

      <label class="field">
        <span>{{ t('auth.username') }}</span>
        <input v-model="username" class="ltr" autocomplete="username" required autofocus>
      </label>

      <PasswordField
        v-model="password"
        :label="t('auth.password')"
        autocomplete="current-password"
        required
      />

      <p v-if="error" class="error">{{ error }}</p>

      <button type="submit" :disabled="busy">{{ busy ? t('auth.signingIn') : t('auth.signIn') }}</button>
    </form>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-card { width: 100%; max-width: 340px; }
.login-card h1 { margin-bottom: .1rem; }
.login-card button { width: 100%; margin-top: .4rem; }
</style>
