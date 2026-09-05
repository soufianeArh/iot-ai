<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { usePoll, fmtTime } from '../usePoll'
import { labelText, modelText } from '../i18n/classLabels'
import ImageLightbox from '../components/ImageLightbox.vue'

const { t, locale } = useI18n()

const cameras = ref([])
const tasks = ref({})       // cameraId -> task
const models = ref([])
const summary = ref([])
const shots = ref([])
const chosen = ref({})      // cameraId -> model string selected in the dropdown
const busy = ref(false)

// The snapshot open full-screen; a 120px thumbnail is too small to check
// whether the box is actually around what it claims.
const zoomed = ref({ src: '', caption: '' })

function openShot(d) {
  zoomed.value = {
    src: d.snapshotUrl,
    caption: `${labelText(d.label, locale.value)} ${d.confidence.toFixed(2)} · ${t('common.camera')} ${d.cameraId}`,
  }
}

const { error, loading, refresh } = usePoll(async () => {
  const [cams, running, mods, sum, dets] = await Promise.all([
    api.cameras(),
    api.tasks(),
    models.value.length ? Promise.resolve(models.value) : api.models(),
    api.detectionSummary(1440),
    // 36, not 12: with only a dozen, everything fit inside the 3-row cap and
    // there was nothing left to scroll to.
    api.detections({ limit: 36 }),
  ])
  cameras.value = cams
  tasks.value = Object.fromEntries(running.map((x) => [x.cameraId, x]))
  models.value = mods

  // Preselect, or the box renders blank and Start silently sends no model,
  // falling back to `default` and missing any fire/plant rule.
  for (const camera of cams) {
    if (!chosen.value[camera.id]) chosen.value[camera.id] = 'default'
  }
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
              <!-- Shows the actual running model, so a wrong-weights start is
                   visible. Translated for display; :value stays the raw key. -->
              <span v-if="tasks[c.id]?.running">{{ modelText(tasks[c.id].model, locale) }}</span>
              <select v-else v-model="chosen[c.id]">
                <option v-for="m in modelOptions()" :key="m" :value="m">{{ modelText(m, locale) }}</option>
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
    <div class="table-wrap scroll-rows" style="--rows: 10">
      <table>
        <thead>
          <tr><th>{{ t('common.camera') }}</th><th>{{ t('common.label') }}</th><th>{{ t('common.count') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in summary" :key="i">
            <td>{{ r.cameraId }}</td>
            <td>{{ labelText(r.label, locale) }}</td>
            <td>{{ $n(r.count, 'plain') }}</td>
          </tr>
          <tr v-if="!summary.length"><td colspan="3" class="hint">{{ t('common.none') }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2>{{ t('detections.recentFrames') }}</h2>
    <!-- --row-h is the height of one figure: a 68px thumbnail plus its caption
         and the grid gap. Three of those, then it scrolls. -->
    <div class="grid scroll-rows" style="--rows: 3; --row-h: 7.2rem">
      <figure v-for="d in shots" :key="d.id" style="margin:0">
        <img v-if="d.snapshotUrl" class="thumb clickable" :src="d.snapshotUrl"
             :alt="labelText(d.label, locale)" loading="lazy" @click="openShot(d)">
        <figcaption class="hint">
          {{ labelText(d.label, locale) }}
          {{ $n(d.confidence, 'decimal') }}
          · {{ t('common.camera') }} {{ d.cameraId }}
          · {{ fmtTime(d.detectedAt, locale) }}
        </figcaption>
      </figure>
    </div>
    <p v-if="!shots.length" class="hint">{{ t('common.none') }}</p>
  </div>

  <ImageLightbox :src="zoomed.src" :caption="zoomed.caption"
                 @close="zoomed = { src: '', caption: '' }" />
</template>
