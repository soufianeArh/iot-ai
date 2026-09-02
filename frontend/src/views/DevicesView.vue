<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { usePoll, fmtTime } from '../usePoll'
import { severityText as severityTextRaw } from '../i18n/severity'
import TimeSeriesChart from '../components/TimeSeriesChart.vue'

const { t, locale } = useI18n()
const severityText = (sev) => severityTextRaw(sev, t)
const devices = ref([])
const properties = ref({})   // device id -> latest property rows
const form = ref({ name: '', deviceCode: '', productKey: '' })
const busy = ref(false)
const formError = ref('')

// ---- chart state ---------------------------------------------------------
const property = ref('temperature')
const minutes = ref(60)
const history = ref({})      // device id -> [{t, v}]
const rules = ref([])
const unregistered = ref([]) // deviceCode/productKey pairs seen but not registered

// The device the dashboard is about. One sensor at a time: comparing two on
// shared axes was pretty but answered the wrong question - you look at a
// dashboard to judge ONE thing, and thresholds only mean something against
// the device they apply to.
const selectedId = ref(null)

const selected = computed(() =>
  devices.value.find((d) => d.id === selectedId.value) || null)

// One colour per device, from the brand ramp. Not the status greens and reds:
// a line on a chart is not a health signal, and reusing those would make an
// ordinary reading look like a verdict.
const LINE_COLOURS = ['#1761ae', '#c2610a', '#2f7d5c', '#7c4dbe', '#a4231f']

const propertyKeys = computed(() => {
  const keys = new Set()
  for (const rows of Object.values(properties.value)) {
    for (const p of rows) keys.add(p.key)
  }
  return [...keys].sort()
})

const series = computed(() => {
  const device = selected.value
  const points = device ? history.value[device.id] || [] : []
  return points.length
    ? [{ name: device.name, colour: LINE_COLOURS[0], points }]
    : []
})

// Thresholds from the device rules that watch this property, drawn on the
// chart. This is the bit that connects the dashboard to the alerting: you can
// see why a rule fired, and how close it came the rest of the time.
// Rules that actually apply to THIS device and THIS property. A rule with no
// deviceCode is a wildcard and applies to every device, which is why it is
// included rather than filtered out.
const relatedRules = computed(() => {
  const device = selected.value
  if (!device) return []
  return rules.value.filter((r) =>
    r.kind === 'device' && r.enabled
    && (r.propertyKey || '').toLowerCase() === property.value.toLowerCase()
    && (!r.deviceCode || r.deviceCode === device.deviceCode))
})

const markers = computed(() =>
  relatedRules.value.map((r) => ({
    value: r.threshold,
    label: `${r.name} ${r.operator} ${r.threshold}`,
  })))

const { error, loading, refresh } = usePoll(async () => {
  devices.value = await api.devices()
  const entries = await Promise.all(devices.value.map(async (d) => {
    try { return [d.id, await api.deviceProperties(d.id)] } catch { return [d.id, []] }
  }))
  properties.value = Object.fromEntries(entries)

  // Default to the first device that is actually reporting, so the page opens
  // on something worth looking at rather than an empty chart.
  if (selectedId.value === null || !devices.value.some((d) => d.id === selectedId.value)) {
    const reporting = devices.value.find((d) => (properties.value[d.id] || []).length)
    selectedId.value = (reporting || devices.value[0] || {}).id ?? null
  }
  await loadHistory()
  try { unregistered.value = await api.unregisteredDevices() } catch { unregistered.value = [] }
})

function selectDevice(device) {
  selectedId.value = device.id
  loadHistory()
}

async function loadHistory() {
  // The window is applied client-side because the API takes a row limit, not
  // a time range. Asking for a generous limit and trimming is one round trip;
  // adding a `since` parameter would be the better fix if this ever grows.
  const wanted = Math.min(500, Math.ceil((minutes.value * 60) / 15) + 20)
  // Only the selected device. Fetching every device's history to draw one
  // line is a request per device per poll, for data nothing displays.
  const targets = selected.value ? [selected.value] : []
  const entries = await Promise.all(targets.map(async (d) => {
    try {
      const rows = await api.deviceHistory(d.id, property.value, wanted)
      const cutoff = Date.now() - minutes.value * 60 * 1000
      const points = rows
        .map((r) => ({ t: r.recordedAt, v: Number(r.value) }))
        .filter((p) => Number.isFinite(p.v) && +new Date(p.t) >= cutoff)
        .sort((a, b) => +new Date(a.t) - +new Date(b.t))   // API returns newest first
      return [d.id, points]
    } catch { return [d.id, []] }
  }))
  history.value = Object.fromEntries(entries)
}

onMounted(async () => {
  try { rules.value = await api.rules() } catch { rules.value = [] }
})

// The topic a device must publish to is iot/{productKey}/{deviceCode}/properties
// (see device-service's MqttSubscriber) - not something the form submits, so it
// is only ever discoverable by reading the backend. Building it here from the
// same two fields the form already has means whoever is wiring up the physical
// device can just copy it, live, before the device even exists yet.
const BROKER_URL = `mqtt://${window.location.hostname}:1883`
const EXAMPLE_PAYLOAD = JSON.stringify({ temperature: 22.4, humidity: 58.1 }, null, 2)

function topicFor(productKey, deviceCode) {
  return `iot/${productKey || '{productKey}'}/${deviceCode || '{deviceCode}'}/properties`
}

const previewTopic = computed(() =>
  topicFor(form.value.productKey.trim(), form.value.deviceCode.trim()))

const selectedTopic = computed(() =>
  selected.value ? topicFor(selected.value.productKey, selected.value.deviceCode) : '')

async function addDevice() {
  formError.value = ''
  busy.value = true
  try {
    await api.addDevice({
      name: form.value.name.trim(),
      deviceCode: form.value.deviceCode.trim(),
      productKey: form.value.productKey.trim(),
    })
    form.value = { name: '', deviceCode: '', productKey: '' }
    await refresh()
  } catch (e) {
    formError.value = e.message
  } finally {
    busy.value = false
  }
}

async function remove(device) {
  if (!confirm(t('devices.confirmDelete', { name: device.name }))) return
  await api.deleteDevice(device.id)
  await refresh()
}

function latest(device, key) {
  return (properties.value[device.id] || []).find((p) => p.key === key)
}
</script>

<template>
  <h1>{{ t('devices.title') }}</h1>
  <p class="page-hint">{{ t('devices.hint') }}</p>
  <p v-if="error" class="error">{{ error }}</p>

  <!-- ---- the selected sensor ---- -->
  <div v-if="selected" class="card">
    <h2 style="margin-bottom:.2rem">{{ selected.name }}</h2>
    <div class="hint" style="margin-bottom:.7rem">
      <code class="mono">{{ selected.deviceCode }}</code>
      <span class="pill" :class="selected.status === 'ONLINE' ? 'ok' : 'bad'"
            style="margin-inline-start:.4rem">{{ selected.status }}</span>
      <span v-if="(properties[selected.id] || []).length" style="margin-inline-start:.6rem">
        {{ fmtTime((properties[selected.id][0] || {}).recordedAt, locale) }}
      </span>
    </div>
    <div class="hint mqtt-line">
      {{ t('devices.broker') }} <code class="mono">{{ BROKER_URL }}</code>
      · {{ t('devices.topicLabel') }} <code class="mono">{{ selectedTopic }}</code>
    </div>

    <div v-if="!(properties[selected.id] || []).length" class="hint">
      {{ t('devices.noProperties') }}
    </div>
    <div v-else class="grid">
      <div v-for="p in properties[selected.id]" :key="p.key" class="metric">
        <div class="hint">{{ p.key }}</div>
        <div class="value">{{ p.value }}</div>
      </div>
    </div>
  </div>
  <div v-else-if="!loading" class="card hint">{{ t('devices.selectHint') }}</div>

  <!-- ---- history ---- -->
  <div class="card">
    <h2>{{ t('devices.history') }}<span v-if="selected"> — {{ selected.name }}</span></h2>
    <div class="row" style="margin-bottom:.6rem">
      <select v-model="property" class="ltr" dir="ltr" style="width:auto"
              @change="loadHistory">
        <option v-for="k in propertyKeys" :key="k" :value="k">{{ k }}</option>
      </select>
      <select v-model.number="minutes" style="width:auto" @change="loadHistory">
        <option :value="60">{{ t('devices.lastHour') }}</option>
        <option :value="1440">{{ t('devices.lastDay') }}</option>
      </select>
    </div>

    <TimeSeriesChart :series="series" :markers="markers" :height="220" />

    <!-- Listed as well as drawn: a dashed line tells you a limit exists, but
         not whether it is scoped to this sensor or applies to every one. -->
    <div v-if="relatedRules.length" class="rules-note">
      <div class="hint">{{ t('devices.relatedRules') }}</div>
      <div v-for="r in relatedRules" :key="r.id" class="rule-line">
        <span class="pill" :class="r.severity">{{ severityText(r.severity) }}</span>
        <b>{{ r.name }}</b>
        <code class="mono">{{ r.propertyKey }} {{ r.operator }} {{ r.threshold }}</code>
        <span class="hint">
          {{ r.deviceCode ? r.deviceCode : t('alerts.anyDevice') }}
          · {{ t('alerts.cooldown') }} {{ r.cooldownSeconds }}s
        </span>
      </div>
    </div>
    <p class="hint" v-if="markers.length">{{ t('devices.thresholdHint') }}</p>
    <p class="hint" v-else>{{ t('devices.noRuleForProperty') }}</p>
  </div>

  <!-- ---- add / manage ---- -->
  <div class="card">
    <h2>{{ t('devices.addDevice') }}</h2>
    <form class="grid" @submit.prevent="addDevice">
      <label class="field">
        <span>{{ t('common.name') }}</span>
        <input v-model="form.name" required maxlength="128">
      </label>
      <label class="field">
        <span>{{ t('devices.code') }}</span>
        <!-- Machine-facing: this string is the MQTT topic segment a device
             publishes under, so it stays Latin and must not be autocapitalised
             into something that never matches an incoming message. -->
        <input v-model="form.deviceCode" class="ltr" required maxlength="64"
               dir="ltr" lang="en" spellcheck="false"
               autocapitalize="off" autocomplete="off" placeholder="C900">
      </label>
      <label class="field">
        <span>{{ t('devices.productKey') }}</span>
        <input v-model="form.productKey" class="ltr" required maxlength="64"
               dir="ltr" lang="en" spellcheck="false"
               autocapitalize="off" autocomplete="off" placeholder="pk-test">
      </label>
      <div class="field" style="align-self:end">
        <button type="submit" :disabled="busy">{{ t('common.add') }}</button>
      </div>
    </form>
    <p class="hint">{{ t('devices.topicHint') }}</p>
    <div class="mqtt-info">
      <div class="hint">{{ t('devices.mqttConnect') }}</div>
      <div class="rule-line">
        <span class="hint">{{ t('devices.broker') }}</span>
        <code class="mono">{{ BROKER_URL }}</code>
      </div>
      <div class="rule-line">
        <span class="hint">{{ t('devices.topicLabel') }}</span>
        <code class="mono">{{ previewTopic }}</code>
      </div>
      <div class="hint" style="margin-top:.3rem">{{ t('devices.payloadExample') }}</div>
      <pre class="mono payload-example">{{ EXAMPLE_PAYLOAD }}</pre>
    </div>
    <p v-if="formError" class="error">{{ formError }}</p>
  </div>

  <!-- MQTT traffic for a code/key nothing is registered under - most often a
       typo in firmware, or a device someone forgot to add here. -->
  <div v-if="unregistered.length" class="card">
    <h2>{{ t('devices.unregisteredTitle') }}</h2>
    <p class="hint">{{ t('devices.unregisteredHint') }}</p>
    <div class="table-wrap scroll-rows" style="--rows: 5">
      <table>
        <thead>
          <tr>
            <th>{{ t('devices.code') }}</th>
            <th>{{ t('devices.productKey') }}</th>
            <th>{{ t('common.count') }}</th>
            <th>{{ t('devices.lastSeen') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in unregistered" :key="u.productKey + '/' + u.deviceCode">
            <td><code class="mono">{{ u.deviceCode }}</code></td>
            <td><code class="mono">{{ u.productKey }}</code></td>
            <td>{{ u.count }}</td>
            <td>{{ fmtTime(u.lastSeenAt, locale) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="table-wrap scroll-rows" style="--rows: 10">
      <table>
        <thead>
          <tr>
            <th>{{ t('common.name') }}</th>
            <th>{{ t('devices.code') }}</th>
            <th>{{ t('common.status') }}</th>
            <th>{{ t('devices.properties') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in devices" :key="d.id"
              class="pick" :class="{ active: d.id === selectedId }"
              @click="selectDevice(d)">
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
                <!-- The API returns `key` and `value`, not propertyKey /
                     propertyValue. Reading the wrong names rendered every pill
                     blank while the data was there all along. -->
                <span v-for="p in properties[d.id]" :key="p.key" class="pill idle">
                  {{ p.key }}: {{ p.value }}
                </span>
              </div>
            </td>
            <!-- .stop, or deleting a row would also select it on the way out. -->
            <td><button class="danger" @click.stop="remove(d)">{{ t('common.delete') }}</button></td>
          </tr>
          <tr v-if="!devices.length && !loading">
            <td colspan="5" class="hint">{{ t('common.none') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.metric { padding: .1rem 0; }
.metric .value { font-size: 1.7rem; font-weight: 700; line-height: 1.1; }

.rules-note { margin: .6rem 0 .2rem; }
.rule-line { display: flex; align-items: center; gap: .45rem; flex-wrap: wrap;
             padding: .15rem 0; font-size: .85rem; }

.mqtt-line code { margin-inline-start: .25rem; }
.mqtt-info { margin-top: .6rem; padding-top: .6rem; border-top: 1px dashed var(--border, #d8d8d8); }
.payload-example { margin: .3rem 0 0; padding: .5rem .6rem; background: var(--surface-2, #f4f4f4);
                    border-radius: 6px; font-size: .82rem; overflow-x: auto; direction: ltr; }

.pick { cursor: pointer; }
/* border-inline-start, so the marker sits on the leading edge in both
   directions - on the right in Arabic - without an RTL-specific rule. */
.pick.active { background: var(--brand-100); box-shadow: inset 3px 0 0 var(--brand-600); }
:global([dir="rtl"]) .pick.active { box-shadow: inset -3px 0 0 var(--brand-600); }
</style>
