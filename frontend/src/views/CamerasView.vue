<script setup>
import { ref, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { usePoll } from '../usePoll'

const { t } = useI18n()
const cameras = ref([])
const form = ref({ name: '', rtspUrl: '' })
const busy = ref(false)
const formError = ref('')
const status = ref('')

// Which camera is being watched, and the HLS url the server told us to use.
// The url comes from the API rather than being built here on purpose: the
// cam{id} naming is the server's business, and hardcoding it in the client is
// how the two drift apart.
const watching = ref(null)
const hlsUrl = ref('')
const videoEl = ref(null)
let hls = null

const { error, loading, refresh } = usePoll(async () => {
  cameras.value = await api.cameras()
})

async function addCamera() {
  formError.value = ''
  busy.value = true
  try {
    await api.addCamera({ name: form.value.name.trim(), rtspUrl: form.value.rtspUrl.trim() })
    form.value = { name: '', rtspUrl: '' }
    await refresh()
  } catch (e) {
    formError.value = e.message
  } finally {
    busy.value = false
  }
}

async function remove(camera) {
  if (watching.value === camera.id) stopWatching()
  await api.deleteCamera(camera.id)
  await refresh()
}

async function probe(camera) {
  busy.value = true
  try { await api.probeCamera(camera.id); await refresh() } finally { busy.value = false }
}

async function watch(camera) {
  stopWatching()
  busy.value = true
  status.value = t('cameras.starting')
  formError.value = ''
  try {
    // POST configures the path on the media server. Idempotent and cheap, so
    // it also self-heals: MediaMTX keeps paths in memory only, and a restart
    // wipes them while the database still lists the camera.
    const info = await api.startStream(camera.id)
    watching.value = camera.id
    hlsUrl.value = info.hlsUrl

    // THE WARM-UP. Do not remove this.
    //
    // The stream is pulled on demand, so the FIRST playlist request has to
    // wake MediaMTX, which then dials the camera over RTSP - measured at
    // ~20s here. hls.js gives up after 10s and renders nothing at all, with
    // no error a user would notice. So the wait happens in a plain fetch,
    // which has no such timeout, and hls.js only ever sees a warm URL.
    //
    // Losing this when porting from the old page is exactly why "watch"
    // silently showed a black box.
    await warm(info.hlsUrl)

    status.value = ''
    await attach(info.hlsUrl)
  } catch (e) {
    status.value = ''
    formError.value = `${t('cameras.startFailed')}: ${e.message}`
    watching.value = null
  } finally {
    busy.value = false
  }
}

/** Fetch the playlist until it answers, so hls.js never meets a cold path. */
async function warm(url, attempts = 8) {
  let last = ''
  for (let i = 0; i < attempts; i++) {
    try {
      // same-origin so the HLS session cookie MediaMTX sets is kept.
      const r = await fetch(url, { credentials: 'same-origin' })
      if (r.ok) return
      last = `HTTP ${r.status}`
    } catch (e) {
      last = e.message
    }
    await new Promise((r) => setTimeout(r, 3000))
  }
  throw new Error(last || 'timed out')
}

async function attach(url) {
  await new Promise((r) => setTimeout(r))       // let the <video> render
  const el = videoEl.value
  if (!el) return

  if (el.canPlayType('application/vnd.apple.mpegurl')) {
    el.src = url                                 // Safari plays HLS natively
    el.play().catch(() => {})
    return
  }

  // hls.js is loaded from the page rather than bundled: it is only needed on
  // this one view, and only on browsers without native HLS.
  if (!window.Hls) await loadHlsJs()
  if (!window.Hls || !window.Hls.isSupported()) {
    formError.value = 'this browser cannot play HLS'
    return
  }

  hls = new window.Hls({ liveDurationInfinity: true })
  hls.loadSource(url)
  hls.attachMedia(el)
  // autoplay never fires without a src, so playback is started explicitly
  // once the manifest is parsed. Allowed because the element is muted.
  hls.on(window.Hls.Events.MANIFEST_PARSED, () => el.play().catch(() => {}))
  // Without this a fatal error is completely silent - the old page had the
  // same handler and it is the only way a user learns anything went wrong.
  hls.on(window.Hls.Events.ERROR, (_, d) => {
    if (d.fatal) formError.value = `playback error: ${d.details}`
  })
}

function loadHlsJs() {
  return new Promise((resolve) => {
    const s = document.createElement('script')
    s.src = 'https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js'
    s.onload = resolve
    s.onerror = resolve
    document.head.appendChild(s)
  })
}

function stopWatching() {
  if (hls) { hls.destroy(); hls = null }
  if (videoEl.value) videoEl.value.removeAttribute('src')
  watching.value = null
  hlsUrl.value = ''
}

onUnmounted(stopWatching)
</script>

<template>
  <h1>{{ t('cameras.title') }}</h1>
  <p class="page-hint">{{ t('cameras.hint') }}</p>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="card">
    <h2>{{ t('cameras.addCamera') }}</h2>
    <form class="grid" @submit.prevent="addCamera">
      <label class="field">
        <span>{{ t('common.name') }}</span>
        <!-- Display text: any language, so no dir override. -->
        <input v-model="form.name" required :placeholder="t('cameras.nameHint')">
      </label>
      <label class="field">
        <span>{{ t('cameras.rtspUrl') }}</span>
        <!-- Machine-facing: forced LTR so a URL is not rendered reversed in
             Arabic, and autocapitalize off so phones do not send Rtsp://. -->
        <input v-model="form.rtspUrl" class="ltr" required
               dir="ltr" lang="en" spellcheck="false"
               autocapitalize="off" autocomplete="off"
               placeholder="rtsp://camera.local:8554/stream">
      </label>
      <div class="field" style="align-self:end">
        <button type="submit" :disabled="busy">{{ t('common.add') }}</button>
      </div>
    </form>
    <p class="hint">{{ t('cameras.rtspHint') }}</p>
    <p v-if="formError" class="error">{{ formError }}</p>
  </div>

  <div v-if="watching || status" class="card">
    <h2>{{ t('cameras.watch') }} — <code class="mono">{{ hlsUrl }}</code></h2>
    <video ref="videoEl" controls muted playsinline style="width:100%;max-width:720px;background:#000"></video>
    <p class="hint">{{ status || t('cameras.streamNotReady') }}</p>
    <button class="ghost" @click="stopWatching">{{ t('cameras.stopWatching') }}</button>
  </div>

  <div class="card">
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t('common.name') }}</th>
            <th>{{ t('common.status') }}</th>
            <th>{{ t('cameras.resolution') }}</th>
            <th>{{ t('cameras.rtspUrl') }}</th>
            <th>{{ t('cameras.lastError') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in cameras" :key="c.id">
            <td>{{ c.id }} — {{ c.name }}</td>
            <td>
              <span class="pill" :class="c.status === 'REACHABLE' ? 'ok' : 'bad'">
                {{ c.status === 'REACHABLE' ? t('cameras.reachable') : t('cameras.unreachable') }}
              </span>
            </td>
            <td><span v-if="c.width">{{ c.width }}×{{ c.height }}</span><span v-else>—</span></td>
            <td><code class="mono">{{ c.rtspUrl }}</code></td>
            <td class="hint">{{ c.lastError || '' }}</td>
            <td>
              <div class="row">
                <button class="ghost" :disabled="busy" @click="probe(c)">{{ t('cameras.probe') }}</button>
                <button :disabled="busy || c.status !== 'REACHABLE'" @click="watch(c)">
                  {{ t('cameras.watch') }}
                </button>
                <button class="danger" @click="remove(c)">{{ t('common.delete') }}</button>
              </div>
            </td>
          </tr>
          <tr v-if="!cameras.length && !loading">
            <td colspan="6" class="hint">{{ t('common.none') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
