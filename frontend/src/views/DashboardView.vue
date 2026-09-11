<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { usePoll, fmtTime } from '../usePoll'
import { labelText } from '../i18n/classLabels'
import { severityText as severityTextRaw } from '../i18n/severity'
import ImageLightbox from '../components/ImageLightbox.vue'

const { t, locale } = useI18n()
const router = useRouter()
const severityText = (sev) => severityTextRaw(sev, t)

// The dashboard only sends you to the right page with the camera flagged,
// it never starts a watch or a task itself, the ?highlight= is a transient
// cue the target page clears after a few seconds.
function goWatch(cameraId) {
  router.push({ path: '/cameras', query: { highlight: cameraId } })
}
function goDetect(cameraId) {
  router.push({ path: '/detections', query: { highlight: cameraId } })
}
function goCameraAlerts(cameraId) {
  router.push({ path: '/alerts', query: { camera: cameraId } })
}
function goDevice(deviceId) {
  router.push({ path: '/devices', query: { highlight: deviceId } })
}
function goDeviceAlerts(deviceCode) {
  router.push({ path: '/alerts', query: { device: deviceCode } })
}
function goZone(zoneId) {
  // null is the "no zone" row, DevicesView reads ?zone=none for it.
  router.push({ path: '/devices', query: { zone: zoneId == null ? 'none' : String(zoneId) } })
}

const devices = ref([])
const zones = ref([])
const deviceReadings = ref({}) // device id -> its most recently reported property, or null
const cameras = ref([])
const cameraShots = ref({})    // camera id -> its most recent detection ever, or null
const tasks = ref([])
const models = ref([])
const alertSummary = ref({})
const recentAlerts = ref([])
const openCounts = ref({ byCamera: {}, byDevice: {} })

const { error, loading, refresh } = usePoll(async () => {
  const [d, c, tk, m, s, a, counts, z] = await Promise.all([
    api.devices(),
    api.cameras(),
    api.tasks(),
    models.value.length ? Promise.resolve(models.value) : api.models(),
    api.alertSummary(),
    api.alerts({ limit: 8 }),
    // Real per-camera / per-device open counts and worst severity, computed
    // server side over every unresolved alert, not a capped page of them.
    api.openAlertCounts(),
    api.zones().catch(() => []),
  ])
  devices.value = d
  cameras.value = c
  tasks.value = tk
  models.value = m
  alertSummary.value = s
  recentAlerts.value = a
  openCounts.value = counts
  zones.value = z

  // Latest frame per camera, fetched one at a time: a shared page of recent
  // detections gets swamped by whichever camera is analysed most, dropping a
  // quiet camera's last picture even though it still exists.
  const shotEntries = await Promise.all(c.map(async (camera) => {
    try {
      const rows = await api.detections({ cameraId: camera.id, limit: 8 })
      return [camera.id, rows.find((det) => det.snapshotUrl) || null]
    } catch { return [camera.id, null] }
  }))
  cameraShots.value = Object.fromEntries(shotEntries.filter(([, det]) => det))

  // One row per device: whichever property it reported most recently, not
  // every property, this is a glance summary, not the full Devices page.
  const entries = await Promise.all(d.map(async (device) => {
    try {
      const props = await api.deviceProperties(device.id)
      const latest = props.reduce((a, b) => (!a || b.recordedAt > a.recordedAt ? b : a), null)
      return [device.id, latest]
    } catch { return [device.id, null] }
  }))
  deviceReadings.value = Object.fromEntries(entries)
})

const devicesOnline = computed(() => devices.value.filter((d) => d.status === 'ONLINE').length)
const camerasReachable = computed(() => cameras.value.filter((c) => c.status === 'REACHABLE').length)
const tasksRunning = computed(() => tasks.value.filter((tk) => tk.running).length)

const alertsByCamera = computed(() => openCounts.value.byCamera || {})
const alertsByDevice = computed(() => openCounts.value.byDevice || {})

// deviceCode -> zone name, so an alert row can show which plot the sensor is on.
const zoneByDeviceCode = computed(() => {
  const m = {}
  for (const d of devices.value) if (d.deviceCode) m[d.deviceCode] = d.zoneName
  return m
})

// One row per zone (plus a "no zone" row when some device is unassigned):
// how many of its devices are online, and the worst open alert across them.
const SEV_RANK = { INFO: 1, WARNING: 2, CRITICAL: 3 }
const zoneRollup = computed(() => {
  const byDevice = openCounts.value.byDevice || {}

  const summarize = (id, name, ds) => {
    let alertCount = 0
    let worst = null
    for (const d of ds) {
      const open = byDevice[d.deviceCode]
      if (!open) continue
      alertCount += open.count
      if (!worst || SEV_RANK[open.worstSeverity] > SEV_RANK[worst]) worst = open.worstSeverity
    }
    return {
      id,
      name,
      total: ds.length,
      online: ds.filter((d) => d.status === 'ONLINE').length,
      alertCount,
      worstSeverity: worst,
    }
  }

  const rows = zones.value.map((z) =>
    summarize(z.id, z.name, devices.value.filter((d) => d.zoneId === z.id)))
  const orphans = devices.value.filter((d) => !d.zoneId)
  if (orphans.length) rows.push(summarize(null, t('devices.noZone'), orphans))
  return rows
})

// The camera or alert snapshot open full-screen, same treatment as the
// Cameras and Alerts pages.
const zoomed = ref({ src: '', caption: '' })
function openShot(src, caption) {
  zoomed.value = { src, caption }
}
</script>

<template>
  <h1>{{ t('dashboard.title') }}</h1>
  <p class="page-hint">{{ t('dashboard.hint') }}</p>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="card">
    <h2>{{ t('dashboard.platform') }}</h2>
    <div class="grid">
      <div class="stat-tile">
        <div class="stat">{{ devicesOnline }} / {{ devices.length }}</div>
        <div class="stat-label">{{ t('dashboard.devicesOnline') }}</div>
      </div>
      <div class="stat-tile">
        <div class="stat">{{ camerasReachable }} / {{ cameras.length }}</div>
        <div class="stat-label">{{ t('dashboard.camerasReachable') }}</div>
      </div>
      <div class="stat-tile">
        <div class="stat">{{ tasksRunning }}</div>
        <div class="stat-label">{{ t('dashboard.tasksRunning') }}</div>
      </div>
      <div class="stat-tile">
        <div class="stat">{{ models.length }}</div>
        <div class="stat-label">{{ t('dashboard.modelsAvailable') }}</div>
      </div>
    </div>
  </div>

  <div v-if="zoneRollup.length" class="card">
    <h2>{{ t('dashboard.zones') }}</h2>
    <div class="grid">
      <div v-for="z in zoneRollup" :key="z.id ?? 'none'"
           class="zone-card" :class="{ pick: z.id != null }"
           @click="z.id != null && goZone(z.id)">
        <div class="dev-head">
          <strong>{{ z.name }}</strong>
          <span class="pill idle">{{ z.online }} / {{ z.total }}</span>
        </div>
        <div class="stat-label">{{ t('dashboard.devicesOnline') }}</div>
        <span v-if="z.alertCount" class="pill dev-alert" :class="z.worstSeverity">
          {{ t('dashboard.alertsOpen', { count: $n(z.alertCount, 'plain') }) }}
        </span>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>{{ t('dashboard.cameras') }}</h2>
    <div class="grid">
      <div v-for="c in cameras" :key="c.id" class="camera-card">
        <img v-if="cameraShots[c.id]" class="cam-frame clickable" :src="cameraShots[c.id].snapshotUrl"
             :alt="c.name" loading="lazy"
             @click="openShot(cameraShots[c.id].snapshotUrl, c.name)">
        <div v-else class="cam-frame placeholder">{{ t('dashboard.noSnapshot') }}</div>

        <div class="cam-meta">
          <strong>{{ c.name }}</strong>
          <div class="row">
            <span class="pill" :class="c.status === 'REACHABLE' ? 'ok' : 'bad'">
              {{ c.status === 'REACHABLE' ? t('cameras.reachable') : t('cameras.unreachable') }}
            </span>
            <button v-if="alertsByCamera[c.id]" class="pill" :class="alertsByCamera[c.id].worstSeverity"
                    type="button" @click="goCameraAlerts(c.id)"
                    :title="t('alerts.title')">
              {{ t('dashboard.alertsOpen', { count: $n(alertsByCamera[c.id].count, 'plain') }) }}
            </button>
          </div>
          <div v-if="cameraShots[c.id]" class="hint">{{ fmtTime(cameraShots[c.id].detectedAt, locale) }}</div>
        </div>

        <div class="row cam-actions">
          <button class="ghost" type="button" @click="goWatch(c.id)">{{ t('cameras.watch') }}</button>
          <button class="ghost" type="button" @click="goDetect(c.id)">{{ t('dashboard.detect') }}</button>
        </div>
      </div>
    </div>
    <p v-if="!cameras.length && !loading" class="hint">{{ t('common.none') }}</p>
  </div>

  <div class="card">
    <h2>{{ t('dashboard.deviceReadings') }}</h2>
    <div class="grid">
      <div v-for="d in devices" :key="d.id" class="device-card" @click="goDevice(d.id)">
        <div class="dev-head">
          <strong>{{ d.name }}</strong>
          <span class="pill" :class="d.status === 'ONLINE' ? 'ok' : 'bad'">{{ d.status }}</span>
        </div>
        <div v-if="d.zoneName || d.location" class="hint">
          {{ [d.zoneName, d.location].filter(Boolean).join(' · ') }}
        </div>
        <div v-if="deviceReadings[d.id]">
          <code class="mono">{{ deviceReadings[d.id].key }}</code> = <b>{{ deviceReadings[d.id].value }}</b>
        </div>
        <div v-else class="hint">{{ t('devices.noProperties') }}</div>
        <div class="hint">
          {{ deviceReadings[d.id] ? fmtTime(deviceReadings[d.id].recordedAt, locale) : t('common.never') }}
        </div>
        <button v-if="alertsByDevice[d.deviceCode]" class="pill dev-alert" :class="alertsByDevice[d.deviceCode].worstSeverity"
                type="button" @click.stop="goDeviceAlerts(d.deviceCode)" :title="t('alerts.title')">
          {{ t('dashboard.alertsOpen', { count: $n(alertsByDevice[d.deviceCode].count, 'plain') }) }}
        </button>
      </div>
    </div>
    <p v-if="!devices.length && !loading" class="hint">{{ t('common.none') }}</p>
  </div>

  <div class="card">
    <h2>{{ t('dashboard.alertsOverview') }}</h2>
    <!-- Same fields as the Alerts page's own summary cards, unacknowledged
         plus a card per severity, nothing invented that summary can't back up. -->
    <div class="grid">
      <div class="stat-tile">
        <div class="stat">{{ $n(alertSummary.unacknowledged || 0, 'plain') }}</div>
        <div class="stat-label">{{ t('alerts.openAlerts') }}</div>
      </div>
      <div v-for="(count, sev) in (alertSummary.bySeverity || {})" :key="sev" class="stat-tile">
        <div class="stat">{{ $n(count, 'plain') }}</div>
        <div class="stat-label"><span class="pill" :class="sev">{{ severityText(sev) }}</span></div>
      </div>
    </div>

    <div class="table-wrap" style="margin-top:var(--gap)">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>{{ t('alerts.raised') }}</th>
            <th>{{ t('alerts.severity') }}</th>
            <th>{{ t('alerts.ruleName') }}</th>
            <th>{{ t('common.camera') }}</th>
            <th>{{ t('common.label') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in recentAlerts" :key="a.id">
            <td>
              <img v-if="a.snapshotUrl" class="thumb clickable" :src="a.snapshotUrl"
                   :alt="labelText(a.label, locale)" loading="lazy"
                   @click="openShot(a.snapshotUrl, `${a.ruleName} · ${labelText(a.label, locale)}`)">
            </td>
            <td>{{ fmtTime(a.raisedAt, locale) }}</td>
            <td><span class="pill" :class="a.severity">{{ severityText(a.severity) }}</span></td>
            <td>{{ a.ruleName }}</td>
            <td>
              <template v-if="a.deviceCode">
                <code class="mono">{{ a.deviceCode }}</code>
                <span v-if="zoneByDeviceCode[a.deviceCode]" class="pill idle"
                      style="margin-inline-start:.35rem">{{ zoneByDeviceCode[a.deviceCode] }}</span>
              </template>
              <span v-else>{{ a.cameraId }}</span>
            </td>
            <td>{{ labelText(a.label, locale) }}</td>
          </tr>
          <tr v-if="!recentAlerts.length && !loading">
            <td colspan="6" class="hint">{{ t('common.none') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <ImageLightbox :src="zoomed.src" :caption="zoomed.caption"
                 @close="zoomed = { src: '', caption: '' }" />
</template>

<style scoped>
/* The open-alerts badge navigates to the filtered Alerts page, so it's a
   real button. Keep the pill's severity colours, but a border in that same
   colour (currentColor) and a hover so it reads as clickable, not a label. */
button.pill {
  padding: .14rem .55rem;
  font: inherit;
  font-size: .78rem;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid currentColor;
}
button.pill:hover { filter: brightness(0.95); }

/* A stat inside a card, not a card itself, so no nested card chrome. The
   page-ground background sets it apart from the white card behind it. */
.stat-tile {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: .7rem .9rem;
}

.camera-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: .6rem;
  display: flex;
  flex-direction: column;
  gap: .5rem;
}
.cam-frame {
  width: 100%;
  height: 140px;
  object-fit: cover;
  border-radius: 4px;
  background: #000;
  display: block;
}
.cam-frame.clickable { cursor: zoom-in; }
.cam-frame.placeholder {
  background: transparent;
  border: 1px dashed var(--border);
  color: var(--text-dim);
  font-size: .75rem;
  display: flex; align-items: center; justify-content: center;
}
.cam-meta { display: flex; flex-direction: column; gap: .3rem; }
.cam-actions { margin-top: auto; }
.cam-actions button { flex: 1; }

.device-card, .zone-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: .7rem;
  display: flex;
  flex-direction: column;
  gap: .35rem;
}
.device-card { cursor: pointer; }
.zone-card.pick { cursor: pointer; }
.device-card:hover, .zone-card.pick:hover { border-color: var(--brand-500); }
.dev-head { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
/* the alert badge sits on its own line, not stretched across the card */
.dev-alert { align-self: flex-start; }
</style>
