import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

/**
 * Reads ?highlight=<id> from the route and briefly flashes the row whose
 * element id is `${prefix}${id}`, scrolling it into view. The flash fades on
 * its own (the .row-flash CSS animation), and the flag is cleared after
 * `durationMs` so re-visiting the same id flashes it again.
 *
 * A transient "here's the one you came here for" cue from the dashboard's
 * Watch / Detect buttons, nothing sticky or selectable.
 */
export function useRowHighlight(prefix, durationMs = 4000) {
  const route = useRoute()
  const highlightId = ref(null)
  let timer = null

  function scrollTo(id, attempt = 0) {
    const el = document.getElementById(prefix + id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    // The list is loaded async, so the row may not exist on the first tick.
    if (attempt < 15) setTimeout(() => scrollTo(id, attempt + 1), 200)
  }

  function apply() {
    const raw = route.query.highlight
    if (raw === undefined || raw === null || raw === '') return
    const id = Number(raw)
    if (Number.isNaN(id)) return

    highlightId.value = id
    clearTimeout(timer)
    timer = setTimeout(() => { highlightId.value = null }, durationMs)
    scrollTo(id)
  }

  onMounted(apply)
  watch(() => route.query.highlight, apply)
  onUnmounted(() => clearTimeout(timer))

  return { highlightId }
}
