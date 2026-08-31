<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { usePoll, fmtTime } from '../usePoll'

const { t, locale } = useI18n()

const summary = ref({})
const rules = ref([])
const alerts = ref([])
const cameras = ref([])
const onlyOpen = ref(false)
const busy = ref(false)
const formError = ref('')

// Real class names, fetched once. This is the whole reason the label field is
// a dropdown: typed by hand, "vehicle" or "car" are accepted, saved, and then
// never match anything - the rule looks healthy and silently never fires.
const labels = ref({ all: [], byModel: {} })
const freeText = ref(false)

const blank = {
  name: '', label: 'person', cameraId: '', minConfidence: 0.5,
  minCount: 1, cooldownSeconds: 60, severity: 'WARNING',
}
const form = ref({ ...blank })

const { error, loading, refresh } = usePoll(async () => {
  const [s, r, a, c] = await Promise.all([
    api.alertSummary(),
    api.rules(),
    api.alerts({ limit: 50, ...(onlyOpen.value ? { acknowledged: 'false' } : {}) }),
    cameras.value.length ? Promise.resolve(cameras.value) : api.cameras(),
  ])
  summary.value = s
  rules.value = r
  alerts.value = a
  cameras.value = c
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
</script>

<template>
  <h1>{{ t('alerts.title') }}</h1>
  <p class="page-hint">{{ t('alerts.hint') }}</p>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="grid">
    <!-- Fields match /ai/alerts/summary exactly: unacknowledged, total,
         bySeverity. Inventing `open` and `lastHour` here rendered a confident
         0 next to a total of 457 - a wrong number is worse than no number. -->
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
      <div class="stat-label"><span class="pill" :class="sev">{{ sev }}</span></div>
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
        <span>{{ t('common.label') }}</span>
        <select v-if="!freeText" v-model="form.label" class="ltr" dir="ltr" required>
          <optgroup v-for="(classes, model) in labels.byModel" :key="model" :label="model">
            <option v-for="c in classes" :key="model + c" :value="c">{{ c }}</option>
          </optgroup>
        </select>
        <!-- Machine-facing: must match a class name byte for byte. -->
        <input v-else v-model="form.label" class="ltr" required
               dir="ltr" lang="en" spellcheck="false"
               autocapitalize="off" autocomplete="off" placeholder="person">
      </label>

      <label class="field">
        <span>{{ t('common.camera') }}</span>
        <select v-model="form.cameraId">
          <option value="">{{ t('alerts.anyCamera') }}</option>
          <option v-for="c in cameras" :key="c.id" :value="c.id">{{ c.id }} — {{ c.name }}</option>
        </select>
      </label>

      <label class="field">
        <span>{{ t('alerts.minConfidence') }}</span>
        <input v-model.number="form.minConfidence" type="number" step="0.05" min="0.05" max="1" class="ltr">
      </label>
      <label class="field">
        <span>{{ t('alerts.minCount') }}</span>
        <input v-model.number="form.minCount" type="number" min="1" class="ltr">
      </label>
      <label class="field">
        <span>{{ t('alerts.cooldown') }}</span>
        <input v-model.number="form.cooldownSeconds" type="number" min="0" class="ltr">
      </label>
      <label class="field">
        <span>{{ t('alerts.severity') }}</span>
        <select v-model="form.severity">
          <option>INFO</option><option>WARNING</option><option>CRITICAL</option>
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
    <p class="hint">{{ t('alerts.cooldownHint') }}</p>
    <p v-if="formError" class="error">{{ formError }}</p>
  </div>

  <div class="card">
    <h2>{{ t('alerts.rules') }}</h2>
    <div class="table-wrap">
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
            <td><code class="mono">{{ r.label }}</code></td>
            <td>{{ r.cameraId ?? t('alerts.anyCamera') }}</td>
            <td>{{ $n(r.minConfidence, 'decimal') }}</td>
            <td>{{ r.minCount }}</td>
            <td>{{ r.cooldownSeconds }}s</td>
            <td><span class="pill" :class="r.severity">{{ r.severity }}</span></td>
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
      <input type="checkbox" v-model="onlyOpen" style="width:auto" @change="refresh">
      <span>{{ t('alerts.openAlerts') }}</span>
    </label>
    <div class="table-wrap">
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
            <td><img v-if="a.snapshotUrl" class="thumb" :src="a.snapshotUrl" :alt="a.label" loading="lazy"></td>
            <td>{{ a.ruleName }}</td>
            <td>{{ a.cameraId }}</td>
            <td><code class="mono">{{ a.label }}</code></td>
            <td>{{ a.count }}</td>
            <td><span class="pill" :class="a.severity">{{ a.severity }}</span></td>
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
  </div>
</template>
