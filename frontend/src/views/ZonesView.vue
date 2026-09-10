<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { usePoll, fmtTime } from '../usePoll'

const { t, locale } = useI18n()

const zones = ref([])
const busy = ref(false)
const formError = ref('')
const rowError = ref('')

const blank = { name: '', description: '' }
const form = ref({ ...blank })

// Per-row edit buffer, keyed by zone id.
const edits = ref({})

const { error, loading, refresh } = usePoll(async () => {
  zones.value = await api.zones()
}, 15000)

async function addZone() {
  formError.value = ''
  busy.value = true
  try {
    await api.addZone({ name: form.value.name.trim(), description: form.value.description.trim() || null })
    form.value = { ...blank }
    await refresh()
  } catch (e) {
    formError.value = e.message
  } finally {
    busy.value = false
  }
}

function startEdit(zone) {
  edits.value = { ...edits.value, [zone.id]: { name: zone.name, description: zone.description || '' } }
}
function cancelEdit(id) {
  const next = { ...edits.value }
  delete next[id]
  edits.value = next
}
async function saveEdit(zone) {
  const buf = edits.value[zone.id]
  if (!buf || !buf.name.trim()) return
  rowError.value = ''
  try {
    await api.updateZone(zone.id, { name: buf.name.trim(), description: buf.description.trim() || null })
    cancelEdit(zone.id)
    await refresh()
  } catch (e) {
    rowError.value = e.message
  }
}

async function removeZone(zone) {
  if (!confirm(t('zones.confirmDelete', { name: zone.name, count: zone.deviceCount }))) return
  rowError.value = ''
  try {
    await api.deleteZone(zone.id)
    await refresh()
  } catch (e) {
    rowError.value = e.message
  }
}
</script>

<template>
  <h1>{{ t('zones.title') }}</h1>
  <p class="page-hint">{{ t('zones.hint') }}</p>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="card">
    <h2>{{ t('zones.addZone') }}</h2>
    <form class="grid" @submit.prevent="addZone">
      <label class="field">
        <span>{{ t('common.name') }}</span>
        <input v-model="form.name" required maxlength="128" :placeholder="t('zones.namePlaceholder')">
      </label>
      <label class="field">
        <span>{{ t('zones.description') }}</span>
        <input v-model="form.description" maxlength="500">
      </label>
      <div class="field" style="align-self:end">
        <button type="submit" :disabled="busy">{{ t('common.add') }}</button>
      </div>
    </form>
    <p v-if="formError" class="error">{{ formError }}</p>
  </div>

  <div class="card">
    <p v-if="rowError" class="error">{{ rowError }}</p>
    <div class="table-wrap scroll-rows" style="--rows: 10">
      <table>
        <thead>
          <tr>
            <th>{{ t('common.name') }}</th>
            <th>{{ t('zones.description') }}</th>
            <th>{{ t('zones.deviceCount') }}</th>
            <th>{{ t('profile.createdAt') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="z in zones" :key="z.id">
            <template v-if="edits[z.id]">
              <td><input v-model="edits[z.id].name" maxlength="128"></td>
              <td><input v-model="edits[z.id].description" maxlength="500"></td>
              <td>{{ z.deviceCount }}</td>
              <td>{{ fmtTime(z.createdAt, locale) }}</td>
              <td>
                <div class="row">
                  <button type="button" @click="saveEdit(z)">{{ t('common.save') }}</button>
                  <button class="ghost" type="button" @click="cancelEdit(z.id)">{{ t('common.cancel') }}</button>
                </div>
              </td>
            </template>
            <template v-else>
              <td>{{ z.name }}</td>
              <td class="hint">{{ z.description || '' }}</td>
              <td>{{ z.deviceCount }}</td>
              <td>{{ fmtTime(z.createdAt, locale) }}</td>
              <td>
                <div class="row">
                  <button class="ghost" type="button" @click="startEdit(z)">{{ t('common.edit') }}</button>
                  <button class="danger" type="button" @click="removeZone(z)">{{ t('common.delete') }}</button>
                </div>
              </td>
            </template>
          </tr>
          <tr v-if="!zones.length && !loading">
            <td colspan="5" class="hint">{{ t('common.none') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
