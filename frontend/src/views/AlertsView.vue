<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { usePoll, fmtTime } from '../usePoll'
import { labelText, modelText } from '../i18n/classLabels'
import { severityText as severityTextRaw } from '../i18n/severity'
import ImageLightbox from '../components/ImageLightbox.vue'

const { t, locale } = useI18n()

const summary = ref({})
const rules = ref([])
const alerts = ref([])
const cameras = ref([])
const onlyOpen = ref(false)
const busy = ref(false)
const formError = ref('')

// Pagination for the alerts table: grows the same `limit` on "load more"
// instead of using an OFFSET, so a poll landing mid-load can't duplicate or
// skip a row the way OFFSET pagination could on a table still getting inserts.
const ALERTS_PAGE = 50
const alertsLimit = ref(ALERTS_PAGE)
// A full page back means there may be more; the exact total sits in
// `summary` already; see `alertsTotal` below.
const hasMoreAlerts = computed(() => alerts.value.length >= alertsLimit.value)
// Filtered only by `acknowledged`, so this always matches one of the two
// summary counts below instead of inventing a number.
const alertsTotal = computed(() =>
  onlyOpen.value ? (summary.value.unacknowledged || 0) : (summary.value.total || 0))

function loadMoreAlerts() {
  alertsLimit.value += ALERTS_PAGE
  refresh()
}

function toggleOnlyOpen() {
  alertsLimit.value = ALERTS_PAGE
  refresh()
}

// The alert snapshot open full-screen. Judging an alert means looking at the
// frame that caused it, and a thumbnail is too small to do that.
const zoomed = ref({ src: '', caption: '' })

function openShot(a) {
  zoomed.value = {
    src: a.snapshotUrl,
    caption: `${a.ruleName} · ${labelText(a.label, locale.value)} · ${t('common.camera')} ${a.cameraId}`,
  }
}

// Real class names, fetched once. It's why label is a dropdown and not free
// text: a typed "vehicle" would save fine and just never match anything.
const labels = ref({ all: [], byModel: {} })
const freeText = ref(false)

const devices = ref([])

const blank = {
  name: '', kind: 'detection',
  // detection
  label: 'person', cameraId: '', minConfidence: 0.5, minCount: 1,
  // device
  deviceCode: '', propertyKey: 'temperature', operator: '>', threshold: 35,
  // both
  cooldownSeconds: 60, severity: 'WARNING',
}

// Real property keys already reported by some sensor, so this has the same
// dropdown safety net as the class labels above.
const propertyKeys = ref([])
const form = ref({ ...blank })

const { error, loading, refresh } = usePoll(async () => {
  const [s, r, a, c, d] = await Promise.all([
    api.alertSummary(),
    api.rules(),
    api.alerts({ limit: alertsLimit.value, ...(onlyOpen.value ? { acknowledged: 'false' } : {}) }),
    cameras.value.length ? Promise.resolve(cameras.value) : api.cameras(),
    api.devices().catch(() => []),
  ])
  summary.value = s
  rules.value = r
  alerts.value = a
  cameras.value = c
  devices.value = d

  const keys = new Set(propertyKeys.value)
  await Promise.all(d.map(async (dev) => {
    try {
      for (const p of await api.deviceProperties(dev.id)) keys.add(p.key)
    } catch { /* a device with no readings yet contributes nothing */ }
  }))
  propertyKeys.value = [...keys].sort()
})

onMounted(async () => {
  // Separate from the poll: this one loads model weights server-side, so it is
  // slow the first time and must not run every five seconds.
  try { labels.value = await api.labels() } catch { freeText.value = true }
})

async function addRule() {
  formError.value = ''
  busy.value = true
  try {
    const body = { ...form.value }
    body.cameraId = body.cameraId === '' ? null : Number(body.cameraId)
    body.deviceCode = body.deviceCode === '' ? null : body.deviceCode
    await api.addRule(body)
    form.value = { ...blank }
    await refresh()
  } catch (e) {
    formError.value = e.message
  } finally {
    busy.value = false
  }
}

async function toggle(rule) {
  await api.updateRule(rule.id, { enabled: !rule.enabled })
  await refresh()
}

async function removeRule(rule) {
  if (!confirm(t('alerts.deleteRule'))) return
  await api.deleteRule(rule.id)
  await refresh()
}

async function ack(alert) {
  await api.ackAlert(alert.id)
  await refresh()
}

const severityText = (sev) => severityTextRaw(sev, t)
</script>

<template>
  <h1>{{ t('alerts.title') }}</h1>
  <p class="page-hint">{{ t('alerts.hint') }}</p>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="grid">
    <!-- Fields match /ai/alerts/summary exactly: unacknowledged, total,
         bySeverity, nothing invented that the summary can't back up. -->
    <div class="card">
      <div class="stat">{{ $n(summary.unacknowledged || 0, 'plain') }}</div>
      <div class="stat-label">{{ t('alerts.openAlerts') }}</div>
    </div>
    <div class="card">
      <div class="stat">{{ $n(summary.total || 0, 'plain') }}</div>
      <div class="stat-label">{{ t('alerts.total') }}</div>
    </div>
    <div v-for="(count, sev) in (summary.bySeverity || {})" :key="sev" class="card">
      <div class="stat">{{ $n(count, 'plain') }}</div>
      <div class="stat-label"><span class="pill" :class="sev">{{ severityText(sev) }}</span></div>
    </div>
  </div>

  <div class="card">
    <h2>{{ t('alerts.addRule') }}</h2>
    <form class="grid" @submit.prevent="addRule">
      <label class="field">
        <span>{{ t('alerts.ruleName') }}</span>
        <!-- Human-facing: any language, no dir override. -->
        <input v-model="form.name" required>
      </label>

      <label class="field">
        <span>{{ t('alerts.kind') }}</span>
        <select v-model="form.kind">
          <option value="detection">{{ t('alerts.kindDetection') }}</option>
          <option value="device">{{ t('alerts.kindDevice') }}</option>
        </select>
      </label>

      <label v-if="form.kind === 'detection'" class="field">
        <span>{{ t('common.label') }}</span>
        <!-- Displayed text is translated; :value stays the raw model class
             name. Only the free-text fallback below needs LTR/Latin. -->
        <select v-if="!freeText" v-model="form.label" required>
          <optgroup v-for="(classes, model) in labels.byModel" :key="model"
                    :label="modelText(model, locale)">
            <option v-for="c in classes" :key="model + c" :value="c">{{ labelText(c, locale) }}</option>
          </optgroup>
        </select>
        <!-- Machine-facing: must match a class name byte for byte. -->
        <input v-else v-model="form.label" class="ltr" required
               dir="ltr" lang="en" spellcheck="false"
               autocapitalize="off" autocomplete="off" placeholder="person">
      </label>

      <label v-if="form.kind === 'detection'" class="field">
        <span>{{ t('common.camera') }}</span>
        <select v-model="form.cameraId">
          <option value="">{{ t('alerts.anyCamera') }}</option>
          <option v-for="c in cameras" :key="c.id" :value="c.id">{{ c.id }} — {{ c.name }}</option>
        </select>
      </label>

      <label v-if="form.kind === 'detection'" class="field">
        <span>{{ t('alerts.minConfidence') }}</span>
        <input v-model.number="form.minConfidence" type="number" step="0.05" min="0.05" max="1" class="ltr">
      </label>
      <label v-if="form.kind === 'detection'" class="field">
        <span>{{ t('alerts.minCount') }}</span>
        <input v-model.number="form.minCount" type="number" min="1" class="ltr">
      </label>

      <!-- ---- device rule fields ---- -->
      <label v-if="form.kind === 'device'" class="field">
        <span>{{ t('alerts.device') }}</span>
        <select v-model="form.deviceCode">
          <option value="">{{ t('alerts.anyDevice') }}</option>
          <option v-for="d in devices" :key="d.id" :value="d.deviceCode">
            {{ d.name }} ({{ d.deviceCode }})
          </option>
        </select>
      </label>

      <label v-if="form.kind === 'device'" class="field">
        <span>{{ t('alerts.property') }}</span>
        <!-- Machine-facing: must match the key the device publishes. -->
        <input v-model="form.propertyKey" class="ltr" list="propertyKeys" required
               dir="ltr" lang="en" spellcheck="false"
               autocapitalize="off" autocomplete="off" placeholder="temperature">
        <datalist id="propertyKeys">
          <option v-for="k in propertyKeys" :key="k" :value="k"></option>
        </datalist>
      </label>

      <label v-if="form.kind === 'device'" class="field">
        <span>{{ t('alerts.operator') }}</span>
        <select v-model="form.operator" class="ltr" dir="ltr">
          <option value="&gt;">&gt; {{ t('alerts.above') }}</option>
          <option value="&lt;">&lt; {{ t('alerts.below') }}</option>
        </select>
      </label>

      <label v-if="form.kind === 'device'" class="field">
        <span>{{ t('alerts.threshold') }}</span>
        <input v-model.number="form.threshold" type="number" step="0.1" class="ltr" required>
      </label>
      <label class="field">
        <span>{{ t('alerts.cooldown') }}</span>
        <input v-model.number="form.cooldownSeconds" type="number" min="0" class="ltr">
      </label>
      <label class="field">
        <span>{{ t('alerts.severity') }}</span>
        <select v-model="form.severity">
          <option value="INFO">{{ severityText('INFO') }}</option>
          <option value="WARNING">{{ severityText('WARNING') }}</option>
          <option value="CRITICAL">{{ severityText('CRITICAL') }}</option>
        </select>
      </label>

      <div class="field" style="align-self:end">
        <button type="submit" :disabled="busy">{{ t('common.add') }}</button>
      </div>
    </form>

    <p class="hint">
      {{ t('alerts.labelHint') }}
      <!-- The examples stay English in every locale: a translated `vache`
           would be accepted and would never match a class name. -->
      <code>{{ t('alerts.labelExamples') }}</code>
      <button class="ghost" type="button" @click="freeText = !freeText">
        {{ freeText ? t('alerts.labelPick') : t('alerts.labelFree') }}
      </button>
    </p>
    <p v-if="form.kind === 'device'" class="hint">{{ t('alerts.deviceHint') }}</p>
    <p class="hint">{{ t('alerts.cooldownHint') }}</p>
    <p v-if="formError" class="error">{{ formError }}</p>
  </div>

  <div class="card">
    <h2>{{ t('alerts.rules') }}</h2>
    <div class="table-wrap scroll-rows" style="--rows: 12">
      <table>
        <thead>
          <tr>
            <th>{{ t('alerts.ruleName') }}</th>
            <th>{{ t('common.label') }}</th>
            <th>{{ t('common.camera') }}</th>
            <th>{{ t('alerts.minConfidence') }}</th>
            <th>{{ t('alerts.minCount') }}</th>
            <th>{{ t('alerts.cooldown') }}</th>
            <th>{{ t('alerts.severity') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rules" :key="r.id" :style="r.enabled ? '' : 'opacity:.5'">
            <td>{{ r.name }}</td>
            <td>
              <!-- One column, two meanings: a class name for a detection rule,
                   the property and threshold for a device rule. -->
              <code v-if="r.kind === 'device'" class="mono">
                {{ r.propertyKey }} {{ r.operator }} {{ r.threshold }}
              </code>
              <span v-else>{{ labelText(r.label, locale) }}</span>
            </td>
            <td>
              {{ r.kind === 'device'
                 ? (r.deviceCode || t('alerts.anyDevice'))
                 : (r.cameraId ?? t('alerts.anyCamera')) }}
            </td>
            <td>{{ r.kind === 'device' ? '—' : $n(r.minConfidence, 'decimal') }}</td>
            <td>{{ r.kind === 'device' ? '—' : r.minCount }}</td>
            <td>{{ r.cooldownSeconds }}s</td>
            <td><span class="pill" :class="r.severity">{{ severityText(r.severity) }}</span></td>
            <td>
              <div class="row">
                <button class="ghost" @click="toggle(r)">
                  {{ r.enabled ? t('common.disable') : t('common.enable') }}
                </button>
                <button class="danger" @click="removeRule(r)">{{ t('common.delete') }}</button>
              </div>
            </td>
          </tr>
          <tr v-if="!rules.length && !loading">
            <td colspan="8" class="hint">{{ t('alerts.noRules') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2>{{ t('alerts.title') }}</h2>
    <label class="row" style="margin-bottom:.6rem">
      <input type="checkbox" v-model="onlyOpen" style="width:auto" @change="toggleOnlyOpen">
      <span>{{ t('alerts.openAlerts') }}</span>
    </label>
    <!-- --row-h is larger here: every row carries a 68px thumbnail. -->
    <div class="table-wrap scroll-rows" style="--rows: 8; --row-h: 5.4rem">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>{{ t('alerts.ruleName') }}</th>
            <th>{{ t('common.camera') }}</th>
            <th>{{ t('common.label') }}</th>
            <th>{{ t('common.count') }}</th>
            <th>{{ t('alerts.severity') }}</th>
            <th>{{ t('alerts.raised') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in alerts" :key="a.id">
            <td>
              <img v-if="a.snapshotUrl" class="thumb clickable" :src="a.snapshotUrl"
                   :alt="labelText(a.label, locale)" loading="lazy" @click="openShot(a)">
            </td>
            <td>{{ a.ruleName }}</td>
            <td>
              <span v-if="a.deviceCode"><code class="mono">{{ a.deviceCode }}</code></span>
              <span v-else>{{ a.cameraId }}</span>
            </td>
            <td>{{ labelText(a.label, locale) }}</td>
            <!-- A device alert has no count; it has a reading. -->
            <td>{{ a.reading !== null ? $n(a.reading, 'decimal') : a.count }}</td>
            <td><span class="pill" :class="a.severity">{{ severityText(a.severity) }}</span></td>
            <td>{{ fmtTime(a.raisedAt, locale) }}</td>
            <td>
              <span v-if="a.acknowledged" class="pill ok">{{ t('alerts.acknowledged') }}</span>
              <button v-else class="ghost" @click="ack(a)">{{ t('alerts.acknowledge') }}</button>
            </td>
          </tr>
          <tr v-if="!alerts.length && !loading">
            <td colspan="8" class="hint">{{ t('common.none') }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- The number the table can't show on its own: the summary counts every
         alert ever raised, the table only what has been paged in so far. -->
    <div v-if="alerts.length" class="row" style="margin-top:.6rem; justify-content:space-between">
      <span class="hint">{{ t('alerts.showingCount', { shown: alerts.length, total: alertsTotal }) }}</span>
      <button v-if="hasMoreAlerts" class="ghost" type="button" :disabled="loading"
              @click="loadMoreAlerts">
        {{ t('alerts.loadMore') }}
      </button>
    </div>
  </div>

  <ImageLightbox :src="zoomed.src" :caption="zoomed.caption"
                 @close="zoomed = { src: '', caption: '' }" />
</template>
