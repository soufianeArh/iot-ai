<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { usePoll, fmtTime } from '../usePoll'

const { t, locale } = useI18n()

const cameras = ref([])
const tasks = ref({})       // cameraId -> task
const models = ref([])
const summary = ref([])
const shots = ref([])
const chosen = ref({})      // cameraId -> model string selected in the dropdown
const busy = ref(false)

const { error, loading, refresh } = usePoll(async () => {
  const [cams, running, mods, sum, dets] = await Promise.all([
    api.cameras(),
    api.tasks(),
    models.value.length ? Promise.resolve(models.value) : api.models(),
    api.detectionSummary(1440),
    api.detections({ limit: 12 }),
  ])
  cameras.value = cams
  tasks.value = Object.fromEntries(running.map((x) => [x.cameraId, x]))
  models.value = mods
  summary.value = sum
  shots.value = dets
})

/** default, fire, and the combination - the combination is usually what you want. */
function modelOptions() {
  const names = models.value.map((m) => m.name)
  return names.length > 1 ? [...names, names.join(',')] : names
}

async function start(cameraId) {
  busy.value = true
  try {
    // Sent explicitly. Omitting it silently starts on `default` alone, and a
    // fire rule on that camera then never fires with nothing to explain why.
    await api.startTask(cameraId, chosen.value[cameraId] || '')
    await refresh()
  } finally { busy.value = false }
}

async function stop(cameraId) {
  busy.value = true
  try { await api.stopTask(cameraId); await refresh() } finally { busy.value = false }
}
</script>

<template>
  <h1>{{ t('detections.title') }}</h1>
  <p class="page-hint">{{ t('detections.hint') }}</p>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="card">
    <h2>{{ t('detections.tasks') }}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t('common.camera') }}</th>
            <th>{{ t('detections.running') }}</th>
            <th>{{ t('detections.framesAnalysed') }}</th>
            <th>{{ t('detections.detectionsSaved') }}</th>
            <th>{{ t('common.error') }}</th>
            <th>{{ t('common.model') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in cameras" :key="c.id">
            <td>{{ c.id }} — {{ c.name }}</td>
            <td>
              <span class="pill" :class="tasks[c.id]?.running ? 'ok' : 'idle'">
                {{ tasks[c.id]?.running ? t('detections.running') : t('detections.notRunning') }}
              </span>
            </td>
            <td>{{ tasks[c.id]?.framesAnalysed ?? '—' }}</td>
            <td>{{ tasks[c.id]?.detectionsSaved ?? '—' }}</td>
            <td class="hint">{{ tasks[c.id]?.lastError || '' }}</td>
            <td>
              <!-- Running: show what it is actually using, which is the only
                   way to notice a camera started on the wrong weights. -->
              <code v-if="tasks[c.id]?.running" class="mono">{{ tasks[c.id].model }}</code>
              <select v-else v-model="chosen[c.id]" class="ltr" dir="ltr">
                <option v-for="m in modelOptions()" :key="m" :value="m">{{ m }}</option>
              </select>
            </td>
            <td>
              <button v-if="tasks[c.id]?.running" class="ghost" :disabled="busy" @click="stop(c.id)">
                {{ t('common.stop') }}
              </button>
              <button v-else :disabled="busy || c.status !== 'REACHABLE'" @click="start(c.id)">
                {{ t('common.start') }}
              </button>
            </td>
          </tr>
          <tr v-if="!cameras.length && !loading">
            <td colspan="7" class="hint">{{ t('common.none') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="hint">{{ t('detections.modelHint') }}</p>
  </div>

  <div class="card">
    <h2>{{ t('detections.byLabel') }}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>{{ t('common.camera') }}</th><th>{{ t('common.label') }}</th><th>{{ t('common.count') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in summary" :key="i">
            <td>{{ r.cameraId }}</td>
            <td><code class="mono">{{ r.label }}</code></td>
            <td>{{ $n(r.count, 'plain') }}</td>
          </tr>
          <tr v-if="!summary.length"><td colspan="3" class="hint">{{ t('common.none') }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2>{{ t('detections.recentFrames') }}</h2>
    <div class="grid">
      <figure v-for="d in shots" :key="d.id" style="margin:0">
        <img v-if="d.snapshotUrl" class="thumb" :src="d.snapshotUrl" :alt="d.label" loading="lazy">
        <figcaption class="hint">
          <code class="mono">{{ d.label }}</code>
          {{ $n(d.confidence, 'decimal') }}
          · {{ t('common.camera') }} {{ d.cameraId }}
          · {{ fmtTime(d.detectedAt, locale) }}
        </figcaption>
      </figure>
    </div>
    <p v-if="!shots.length" class="hint">{{ t('common.none') }}</p>
  </div>
</template>
