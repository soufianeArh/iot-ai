<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'

const { t, tm } = useI18n()

const question = ref('')
const thread = ref([])      // { role, text, tools? }
const history = ref([])     // what gets sent back - the server keeps no session
const tools = ref([])
const health = ref(null)
const busy = ref(false)
const threadEl = ref(null)

const EXAMPLE_KEYS = ['ok', 'alerts', 'sensors', 'tasks', 'whyNoFire', 'fireToday',
                      'animals', 'people', 'working', 'rules']

onMounted(async () => {
  try { tools.value = await api.chatTools() } catch { /* shown as empty */ }
  try { health.value = await api.chatHealth() } catch { health.value = { reachable: false } }
})

async function ask(text) {
  const q = (text ?? question.value).trim()
  if (!q || busy.value) return

  thread.value.push({ role: 'me', text: q })
  question.value = ''
  busy.value = true
  const pending = { role: 'bot', text: t('ask.thinking'), pending: true }
  thread.value.push(pending)
  await scroll()

  try {
    const body = await api.chat(q, history.value)
    Object.assign(pending, { text: body.answer, tools: body.toolsUsed, pending: false })
    history.value.push({ role: 'user', content: q })
    history.value.push({ role: 'assistant', content: body.answer })
  } catch (e) {
    Object.assign(pending, { text: e.message, error: true, pending: false })
  } finally {
    busy.value = false
    await scroll()
  }
}

async function scroll() {
  await nextTick()
  threadEl.value?.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'end' })
}

/** e.g. "search_alerts(acknowledged=false)" - shown so the tool call is visible. */
function callSignature(call) {
  const args = Object.entries(call.arguments || {})
    .map(([k, v]) => `${k}=${v}`).join(', ')
  return `${call.tool}(${args})`
}
</script>

<template>
  <h1>{{ t('ask.title') }}</h1>

  <div class="card">
    <p><b>{{ t('ask.hint') }}</b></p>
    <p>{{ t('ask.explain') }}</p>
    <p>{{ t('ask.limits') }}</p>

    <details>
      <summary class="hint">{{ t('ask.toolsTitle') }}</summary>
      <ul>
        <li v-for="tool in tools" :key="tool.name">
          <code class="mono">{{ tool.name }}({{ tool.parameters.join(', ') }})</code>
          <div class="hint">{{ tool.description }}</div>
        </li>
      </ul>
    </details>
  </div>

  <p v-if="health && !health.reachable" class="error">
    {{ t('ask.unavailable') }} {{ health.error || '' }}
  </p>

  <div class="card">
    <div class="row" style="margin-bottom:.8rem">
      <button v-for="k in EXAMPLE_KEYS" :key="k" class="ghost" type="button"
              :disabled="busy" @click="ask(t('ask.examples.' + k))">
        {{ t('ask.examples.' + k) }}
      </button>
    </div>

    <div ref="threadEl" class="thread">
      <div v-for="(m, i) in thread" :key="i" class="msg" :class="[m.role, { bad: m.error }]">
        <div style="white-space:pre-wrap">{{ m.text }}</div>
        <div v-if="m.tools && m.tools.length" class="tools hint">
          {{ t('ask.called') }}
          <code v-for="(c, j) in m.tools" :key="j" class="mono">{{ callSignature(c) }}</code>
        </div>
      </div>
    </div>

    <form class="row" style="margin-top:.8rem" @submit.prevent="ask()">
      <input v-model="question" :placeholder="t('ask.placeholder')" style="flex:1" autocomplete="off">
      <button type="submit" :disabled="busy">{{ t('ask.send') }}</button>
    </form>
  </div>
</template>

<style scoped>
.thread { display: flex; flex-direction: column; gap: .6rem; }

.msg {
  padding: .55rem .8rem;
  border-radius: 10px;
  max-width: 85%;
  line-height: 1.5;
}
/* align-self start/end follow the text direction, so the conversation reads
   correctly in Arabic without a mirrored rule. */
.msg.me { align-self: flex-end; background: var(--brand-100); }
.msg.bot { align-self: flex-start; border: 1px solid var(--border); background: #fff; }
.msg.bad { border-color: var(--crit); color: var(--crit); }

.tools { margin-top: .35rem; }
.tools code { margin-inline-end: .3rem; }
</style>
