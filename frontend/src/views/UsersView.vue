<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { usePoll, fmtTime } from '../usePoll'
import PasswordField from '../components/PasswordField.vue'

const { t, locale } = useI18n()

const users = ref([])
const busy = ref(false)
const formError = ref('')
const rowError = ref('')

const blank = { username: '', password: '', displayName: '', role: 'VIEWER' }
const form = ref({ ...blank })

// New password typed per row, before Reset is clicked. Keyed by user id so
// clearing one row's field doesn't touch another's mid-edit.
const resetPasswords = ref({})

const { error, loading, refresh } = usePoll(async () => {
  users.value = await api.users()
}, 15000)

async function addUser() {
  formError.value = ''
  busy.value = true
  try {
    await api.addUser({ ...form.value })
    form.value = { ...blank }
    await refresh()
  } catch (e) {
    formError.value = e.message
  } finally {
    busy.value = false
  }
}

async function changeRole(user, role) {
  rowError.value = ''
  try {
    await api.updateUser(user.id, { role })
    await refresh()
  } catch (e) {
    rowError.value = e.message
    await refresh()   // undo the dropdown's optimistic change on failure
  }
}

async function resetPassword(user) {
  const newPassword = (resetPasswords.value[user.id] || '').trim()
  if (!newPassword) return
  rowError.value = ''
  try {
    await api.updateUser(user.id, { newPassword })
    resetPasswords.value[user.id] = ''
  } catch (e) {
    rowError.value = e.message
  }
}

async function removeUser(user) {
  if (!confirm(t('users.confirmDelete', { name: user.username }))) return
  rowError.value = ''
  try {
    await api.deleteUser(user.id)
    await refresh()
  } catch (e) {
    rowError.value = e.message
  }
}
</script>

<template>
  <h1>{{ t('users.title') }}</h1>
  <p class="page-hint">{{ t('users.hint') }}</p>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="card">
    <h2>{{ t('users.addUser') }}</h2>
    <form class="grid" @submit.prevent="addUser">
      <label class="field">
        <span>{{ t('auth.username') }}</span>
        <input v-model="form.username" class="ltr" required
               dir="ltr" lang="en" spellcheck="false"
               autocapitalize="off" autocomplete="off">
      </label>

      <PasswordField
        v-model="form.password"
        :label="t('auth.password')"
        autocomplete="new-password"
        required
      />

      <label class="field">
        <span>{{ t('profile.displayName') }}</span>
        <input v-model="form.displayName" required>
      </label>

      <label class="field">
        <span>{{ t('users.role') }}</span>
        <select v-model="form.role">
          <option value="ADMIN">{{ t('users.roleAdmin') }}</option>
          <option value="OPERATOR">{{ t('users.roleOperator') }}</option>
          <option value="VIEWER">{{ t('users.roleViewer') }}</option>
        </select>
      </label>

      <div class="field" style="align-self:end">
        <button type="submit" :disabled="busy">{{ t('common.add') }}</button>
      </div>
    </form>
    <p class="hint">{{ t('users.roleHint') }}</p>
    <p v-if="formError" class="error">{{ formError }}</p>
  </div>

  <div class="card">
    <p v-if="rowError" class="error">{{ rowError }}</p>
    <div class="table-wrap scroll-rows" style="--rows: 10">
      <table>
        <thead>
          <tr>
            <th>{{ t('auth.username') }}</th>
            <th>{{ t('profile.displayName') }}</th>
            <th>{{ t('users.role') }}</th>
            <th>{{ t('profile.createdAt') }}</th>
            <th>{{ t('users.resetPassword') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td><code class="mono">{{ u.username }}</code></td>
            <td>{{ u.displayName }}</td>
            <td>
              <select :value="u.role" @change="changeRole(u, $event.target.value)">
                <option value="ADMIN">{{ t('users.roleAdmin') }}</option>
                <option value="OPERATOR">{{ t('users.roleOperator') }}</option>
                <option value="VIEWER">{{ t('users.roleViewer') }}</option>
              </select>
            </td>
            <td>{{ fmtTime(u.createdAt, locale) }}</td>
            <td>
              <div class="row">
                <PasswordField v-model="resetPasswords[u.id]" bare
                               autocomplete="new-password"
                               :placeholder="t('users.newPassword')" />
                <button class="ghost" type="button" :disabled="!resetPasswords[u.id]"
                        @click="resetPassword(u)">
                  {{ t('common.save') }}
                </button>
              </div>
            </td>
            <td><button class="danger" @click="removeUser(u)">{{ t('common.delete') }}</button></td>
          </tr>
          <tr v-if="!users.length && !loading">
            <td colspan="6" class="hint">{{ t('common.none') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
