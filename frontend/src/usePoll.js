import { onMounted, onUnmounted, ref } from 'vue'

/**
 * Run `load` now and every `ms`, and clear the timer on unmount so switching
 * pages doesn't leave old polls running in the background.
 */
export function usePoll(load, ms = 5000) {
  const error = ref('')
  const loading = ref(true)
  let timer = null

  async function run() {
    try {
      await load()
      error.value = ''
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    run()
    timer = setInterval(run, ms)
  })
  onUnmounted(() => clearInterval(timer))

  return { error, loading, refresh: run }
}

/** Short local time, or a dash. Locale-aware, but always Western digits. */
export function fmtTime(value, locale = 'en') {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return new Intl.DateTimeFormat(`${locale}-u-nu-latn`, {
    dateStyle: 'short', timeStyle: 'medium',
  }).format(d)
}
