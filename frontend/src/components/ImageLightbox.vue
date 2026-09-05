<script setup>
/*
 * Full-screen viewer for a snapshot: zoom and pan on what's otherwise just a
 * 120px thumbnail, too small to actually check the model's box.
 *
 * Escape and a click on the backdrop both close it. Page scroll is locked
 * while open so the mouse wheel only zooms, not scrolls the page underneath.
 */
import { ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  src: { type: String, default: '' },
  caption: { type: String, default: '' },
})
const emit = defineEmits(['close'])
const { t } = useI18n()

const MIN = 1
const MAX = 6

const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)
let dragging = false
let originX = 0
let originY = 0

function reset() {
  zoom.value = 1
  panX.value = 0
  panY.value = 0
}

function setZoom(next) {
  const clamped = Math.min(MAX, Math.max(MIN, next))
  zoom.value = clamped
  // Reset pan back at 1x zoom, or the image stays off-centre.
  if (clamped === 1) { panX.value = 0; panY.value = 0 }
}

function onWheel(event) {
  event.preventDefault()
  setZoom(zoom.value * (event.deltaY < 0 ? 1.15 : 1 / 1.15))
}

function onPointerDown(event) {
  if (zoom.value === 1) return
  dragging = true
  originX = event.clientX - panX.value
  originY = event.clientY - panY.value
  event.currentTarget.setPointerCapture(event.pointerId)
}

function onPointerMove(event) {
  if (!dragging) return
  panX.value = event.clientX - originX
  panY.value = event.clientY - originY
}

function onPointerUp() { dragging = false }

function onKey(event) {
  if (event.key === 'Escape') emit('close')
  else if (event.key === '+' || event.key === '=') setZoom(zoom.value * 1.25)
  else if (event.key === '-') setZoom(zoom.value / 1.25)
  else if (event.key === '0') reset()
}

// Handles open/close side effects here so the parent only has to set `src`.
watch(() => props.src, (value) => {
  reset()
  if (value) {
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
  } else {
    document.body.style.overflow = ''
    window.removeEventListener('keydown', onKey)
  }
}, { immediate: true })

onUnmounted(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div v-if="src" class="backdrop" @click.self="emit('close')">
    <div class="bar">
      <span class="caption">{{ caption }}</span>
      <button class="ghost" type="button" :disabled="zoom <= MIN"
              :title="t('common.zoomOut')" @click="setZoom(zoom / 1.25)">&minus;</button>
      <span class="level">{{ Math.round(zoom * 100) }}%</span>
      <button class="ghost" type="button" :disabled="zoom >= MAX"
              :title="t('common.zoomIn')" @click="setZoom(zoom * 1.25)">+</button>
      <button class="ghost" type="button" @click="reset">{{ t('common.reset') }}</button>
      <button type="button" @click="emit('close')">{{ t('common.close') }}</button>
    </div>

    <div class="stage" @wheel="onWheel">
      <img :src="src" :alt="caption"
           :style="{ transform: `translate(${panX}px, ${panY}px) scale(${zoom})`,
                     cursor: zoom > 1 ? (dragging ? 'grabbing' : 'grab') : 'zoom-in' }"
           @pointerdown="onPointerDown" @pointermove="onPointerMove"
           @pointerup="onPointerUp" @pointercancel="onPointerUp"
           @dblclick="zoom > 1 ? reset() : setZoom(2.5)">
    </div>

    <p class="help">{{ t('common.zoomHelp') }}</p>
  </div>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(11, 37, 69, .88);
  z-index: 50;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: .6rem;
  padding: 1rem;
}

.bar {
  display: flex;
  align-items: center;
  gap: .4rem;
  color: #fff;
  max-width: 100%;
}
.bar .caption {
  font-size: .85rem;
  opacity: .85;
  margin-inline-end: auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 45vw;
}
.bar .level { font-size: .8rem; min-width: 3.5rem; text-align: center; opacity: .85; }
.bar button.ghost { color: #fff; border-color: rgba(255, 255, 255, .35); }
.bar button.ghost:hover { background: rgba(255, 255, 255, .15); }

.stage {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  max-width: 100%;
  width: 100%;
}
.stage img {
  max-width: 100%;
  max-height: 78vh;
  transform-origin: center;
  transition: transform .08s linear;
  user-select: none;
  -webkit-user-drag: none;
  border-radius: 4px;
}

.help { color: rgba(255, 255, 255, .6); font-size: .75rem; margin: 0; }
</style>
