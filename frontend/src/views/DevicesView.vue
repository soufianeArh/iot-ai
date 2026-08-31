<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { usePoll, fmtTime } from '../usePoll'

const { t, locale } = useI18n()
const devices = ref([])
const properties = ref({})   // device id -> latest property rows

const { error, loading } = usePoll(async () => {
  devices.value = await api.devices()
  // Properties are per device, so this is N+1 by nature. With a handful of
  // devices it is cheaper than adding a join endpoint; revisit past ~50.
  const entries = await Promise.all(devices.value.map(async (d) => {
    try { return [d.id, await api.deviceProperties(d.id)] } catch { return [d.id, []] }
  }))
  properties.value = Object.fromEntries(entries)
})
</script>

<template>
  <h1>{{ t('devices.title') }}</h1>
  <p class="page-hint">{{ t('devices.hint') }}</p>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="card">
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t('common.name') }}</th>
            <th>{{ t('devices.code') }}</th>
            <th>{{ t('common.status') }}</th>
            <th>{{ t('devices.properties') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in devices" :key="d.id">
            <td>{{ d.name }}</td>
            <td><code class="mono">{{ d.deviceCode }}</code></td>
            <td>
              <span class="pill" :class="d.status === 'ONLINE' ? 'ok' : 'bad'">{{ d.status }}</span>
            </td>
            <td>
              <span v-if="!(properties[d.id] || []).length" class="hint">
                {{ t('devices.noProperties') }}
              </span>
              <div v-else class="row">
                <span v-for="p in properties[d.id]" :key="p.id || p.propertyKey" class="pill idle">
                  {{ p.propertyKey }}: {{ p.propertyValue }}
                  <small v-if="p.recordedAt"> · {{ fmtTime(p.recordedAt, locale) }}</small>
                </span>
              </div>
            </td>
          </tr>
          <tr v-if="!devices.length && !loading">
            <td colspan="4" class="hint">{{ t('common.none') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
