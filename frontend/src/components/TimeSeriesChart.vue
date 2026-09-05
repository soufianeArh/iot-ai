<script setup>
/*
 * A small line chart, drawn as inline SVG instead of pulling in a charting
 * library. It only needs a few series with no zoom or brushing, and this way
 * it inherits the theme colours and RTL flip for free.
 */
import { computed, ref } from 'vue'

const props = defineProps({
  // [{ name, colour, points: [{ t: Date|string, v: number }] }]
  series: { type: Array, default: () => [] },
  height: { type: Number, default: 200 },
  unit: { type: String, default: '' },
  // Horizontal markers, e.g. an alert rule's threshold.
  markers: { type: Array, default: () => [] },   // [{ value, label }]
})

const W = 720                      // viewBox units; the SVG scales to its box
const PAD = { top: 12, right: 14, bottom: 22, left: 44 }

const hover = ref(null)            // { x, points: [{name, colour, v, t}] }

const flat = computed(() =>
  props.series.flatMap((s) => s.points.map((p) => ({ ...p, t: +new Date(p.t) }))))

const bounds = computed(() => {
  const points = flat.value
  if (!points.length) return null

  const times = points.map((p) => p.t)
  const values = points.map((p) => p.v).concat(props.markers.map((m) => m.value))

  let lo = Math.min(...values)
  let hi = Math.max(...values)
  // A flat series would collapse to a zero-height range and divide by zero;
  // padding also stops a line sitting exactly on the frame.
  if (hi - lo < 1e-6) { lo -= 1; hi += 1 }
  const pad = (hi - lo) * 0.12

  return { t0: Math.min(...times), t1: Math.max(...times), lo: lo - pad, hi: hi + pad }
})

const H = computed(() => props.height)

function sx(t) {
  const b = bounds.value
  const span = b.t1 - b.t0 || 1
  return PAD.left + ((t - b.t0) / span) * (W - PAD.left - PAD.right)
}

function sy(v) {
  const b = bounds.value
  const span = b.hi - b.lo || 1
  return PAD.top + (1 - (v - b.lo) / span) * (H.value - PAD.top - PAD.bottom)
}

function path(points) {
  if (!points.length) return ''

  // Break the line instead of connecting across a gap much wider than this
  // series' usual reporting interval, so an outage doesn't look like a
  // smooth reading change. Uses the median gap so it adapts per device.
  const deltas = []
  for (let i = 1; i < points.length; i++) {
    deltas.push(+new Date(points[i].t) - +new Date(points[i - 1].t))
  }
  const sorted = [...deltas].sort((a, b) => a - b)
  const median = sorted.length ? sorted[Math.floor(sorted.length / 2)] : 0
  const gapThreshold = Math.max(median * 4, 2 * 60 * 1000)   // never below 2 minutes

  return points
    .map((p, i) => {
      const cmd = i === 0 || deltas[i - 1] > gapThreshold ? 'M' : 'L'
      return `${cmd}${sx(+new Date(p.t)).toFixed(1)},${sy(p.v).toFixed(1)}`
    })
    .join(' ')
}

/** Four gridlines with real values, rounded to something a human would write. */
const ticks = computed(() => {
  const b = bounds.value
  if (!b) return []
  const out = []
  for (let i = 0; i <= 3; i++) {
    const v = b.lo + ((b.hi - b.lo) * i) / 3
    out.push({ v, y: sy(v) })
  }
  return out
})

const timeLabels = computed(() => {
  const b = bounds.value
  if (!b) return []
  return [b.t0, (b.t0 + b.t1) / 2, b.t1].map((t) => ({
    x: sx(t),
    text: new Intl.DateTimeFormat('en-GB', {
      hour: '2-digit', minute: '2-digit', numberingSystem: 'latn',
    }).format(new Date(t)),
  }))
})

/** Nearest sample in each series to the cursor, for the readout. */
function onMove(event) {
  const b = bounds.value
  if (!b) return
  const box = event.currentTarget.getBoundingClientRect()
  const ratio = (event.clientX - box.left) / box.width
  const t = b.t0 + ratio * (b.t1 - b.t0)

  const picks = props.series.map((s) => {
    let best = null
    for (const p of s.points) {
      const d = Math.abs(+new Date(p.t) - t)
      if (!best || d < best.d) best = { d, p }
    }
    return best ? { name: s.name, colour: s.colour, v: best.p.v, t: best.p.t } : null
  }).filter(Boolean)

  hover.value = picks.length ? { x: sx(t), points: picks } : null
}
</script>

<template>
  <div class="chart">
    <svg v-if="bounds" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none"
         @mousemove="onMove" @mouseleave="hover = null">
      <!-- gridlines and value labels -->
      <g v-for="(tick, i) in ticks" :key="'g' + i">
        <line :x1="PAD.left" :x2="W - PAD.right" :y1="tick.y" :y2="tick.y" class="grid" />
        <text :x="PAD.left - 6" :y="tick.y + 3" class="axis" text-anchor="end">
          {{ tick.v.toFixed(1) }}
        </text>
      </g>

      <!-- rule thresholds: why an alert fired, and how close it came otherwise -->
      <g v-for="(m, i) in markers" :key="'m' + i">
        <line :x1="PAD.left" :x2="W - PAD.right" :y1="sy(m.value)" :y2="sy(m.value)"
              class="marker" />
        <text :x="W - PAD.right" :y="sy(m.value) - 4" class="marker-label" text-anchor="end">
          {{ m.label }}
        </text>
      </g>

      <path v-for="s in series" :key="s.name" :d="path(s.points)"
            class="line" :style="{ stroke: s.colour }" />

      <g v-if="hover">
        <line :x1="hover.x" :x2="hover.x" :y1="PAD.top" :y2="H - PAD.bottom" class="cursor" />
        <circle v-for="p in hover.points" :key="p.name"
                :cx="hover.x" :cy="sy(p.v)" r="3" :style="{ fill: p.colour }" />
      </g>

      <text v-for="(l, i) in timeLabels" :key="'t' + i"
            :x="l.x" :y="H - 6" class="axis" text-anchor="middle">{{ l.text }}</text>
    </svg>

    <p v-else class="hint">—</p>

    <!-- Readout below rather than a floating tooltip: it never covers the line,
         and it needs no RTL-specific positioning. -->
    <div class="readout">
      <span v-for="s in series" :key="s.name" class="key">
        <i :style="{ background: s.colour }"></i>{{ s.name }}
        <b v-if="hover">{{ (hover.points.find((p) => p.name === s.name) || {}).v }}{{ unit }}</b>
      </span>
    </div>
  </div>
</template>

<style scoped>
/* The chart stays LTR even in Arabic: a time axis reading right-to-left
 * would put "now" on the left, which no reader expects. This also keeps
 * text-anchor="end" meaning what it says for the threshold labels. */
.chart svg { width: 100%; display: block; direction: ltr; }
.grid { stroke: var(--border); stroke-width: 1; vector-effect: non-scaling-stroke; }
.line { fill: none; stroke-width: 2; vector-effect: non-scaling-stroke; }
.cursor { stroke: var(--text-dim); stroke-width: 1; stroke-dasharray: 3 3;
          vector-effect: non-scaling-stroke; }
.marker { stroke: var(--crit); stroke-width: 1; stroke-dasharray: 5 4;
          vector-effect: non-scaling-stroke; opacity: .8; }
.marker-label { fill: var(--crit); font-size: 10px; }
.axis { fill: var(--text-dim); font-size: 10px; }

.readout { display: flex; flex-wrap: wrap; gap: .8rem; margin-top: .3rem; font-size: .8rem; }
.readout .key { color: var(--text-dim); display: flex; align-items: center; gap: .3rem; }
.readout i { width: 10px; height: 3px; border-radius: 2px; display: inline-block; }
.readout b { color: var(--text); }
</style>
