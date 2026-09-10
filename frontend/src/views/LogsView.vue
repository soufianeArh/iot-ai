<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { usePoll, fmtTime } from '../usePoll'

const { t, locale } = useI18n()

const rows = ref([])
const expanded = ref(null)

// Filters live in local state, not the URL: this is a single admin screen,
// not something linked to from elsewhere.
const filters = ref({ actor: '', action: '', resource: '' })

const ACTIONS = ['CREATE', 'UPDATE', 'DELETE', 'ACK', 'LOGIN', 'LOGOUT']
const RESOURCES = ['device', 'zone', 'user', 'rule', 'alert', 'camera', 'task', 'session', 'profile']

const { error, loading, refresh } = usePoll(async () => {
  const params = { limit: 300 }
  if (filters.value.actor.trim()) params.actor = filters.value.actor.trim()
  if (filters.value.action) params.action = filters.value.action
  if (filters.value.resource) params.resource = filters.value.resource
  rows.value = await api.audit(params)
}, 20000)

function applyFilters() {
  refresh()
}
function clearFilters() {
  filters.value = { actor: '', action: '', resource: '' }
  refresh()
}

function actionLabel(a) {
  return t(`logs.action.${a}`) !== `logs.action.${a}` ? t(`logs.action.${a}`) : a
}
function resourceLabel(r) {
  if (!r) return ''
  return t(`logs.resource.${r}`) !== `logs.resource.${r}` ? t(`logs.resource.${r}`) : r
}
function outcomeLabel(o) {
  return t(`logs.outcome.${o}`) !== `logs.outcome.${o}` ? t(`logs.outcome.${o}`) : o
}
const outcomePill = { SUCCESS: 'ok', DENIED: 'bad', REJECTED: 'idle', ERROR: 'bad' }

function toggle(id) {
  expanded.value = expanded.value === id ? null : id
}

const hasFilter = computed(() =>
  !!(filters.value.actor.trim() || filters.value.action || filters.value.resource))
</script>

<template>
  <h1>{{ t('logs.title') }}</h1>
  <p class="page-hint">{{ t('logs.hint') }}</p>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="card">
    <div class="row" style="gap:.9rem; flex-wrap:wrap; align-items:flex-end">
      <label class="field" style="width:auto; margin:0">
        <span>{{ t('logs.filterActor') }}</span>
        <input v-model="filters.actor" class="ltr" dir="ltr" spellcheck="false"
               autocapitalize="off" @keyup.enter="applyFilters">
      </label>
      <label class="field" style="width:auto; margin:0">
        <span>{{ t('logs.filterAction') }}</span>
        <select v-model="filters.action">
          <option value="">{{ t('logs.allActions') }}</option>
          <option v-for="a in ACTIONS" :key="a" :value="a">{{ actionLabel(a) }}</option>
        </select>
      </label>
      <label class="field" style="width:auto; margin:0">
        <span>{{ t('logs.filterResource') }}</span>
        <select v-model="filters.resource">
          <option value="">{{ t('logs.allResources') }}</option>
          <option v-for="r in RESOURCES" :key="r" :value="r">{{ resourceLabel(r) }}</option>
        </select>
      </label>
      <button type="button" @click="applyFilters">{{ t('logs.apply') }}</button>
      <button v-if="hasFilter" class="ghost" type="button" @click="clearFilters">{{ t('common.reset') }}</button>
    </div>
  </div>

  <div class="card">
    <div class="table-wrap scroll-rows" style="--rows: 16">
      <table>
        <thead>
          <tr>
            <th>{{ t('logs.colWhen') }}</th>
            <th>{{ t('logs.colWho') }}</th>
            <th>{{ t('logs.colWhat') }}</th>
            <th>{{ t('logs.colResult') }}</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="r in rows" :key="r.id">
            <tr class="pick" @click="toggle(r.id)">
              <td class="ltr" dir="ltr">{{ fmtTime(r.at, locale) }}</td>
              <td>
                <template v-if="r.actor">
                  {{ r.actor }}
                  <span v-if="r.actorRole" class="hint">{{ r.actorRole }}</span>
                </template>
                <span v-else class="hint">{{ t('logs.noActor') }}</span>
              </td>
              <td>
                <span class="pill idle">{{ actionLabel(r.action) }}</span>
                <span v-if="r.resource" style="margin-inline-start:.35rem">
                  {{ resourceLabel(r.resource) }}<span v-if="r.resourceId" class="ltr"> #{{ r.resourceId }}</span>
                </span>
              </td>
              <td><span class="pill" :class="outcomePill[r.outcome] || 'idle'">{{ outcomeLabel(r.outcome) }}</span></td>
            </tr>
            <tr v-if="expanded === r.id" class="detail">
              <td colspan="4">
                <div class="detail-grid ltr" dir="ltr">
                  <span class="hint">service</span><span>{{ r.service }}</span>
                  <span class="hint">method</span><span>{{ r.method }}</span>
                  <span class="hint">path</span><code class="mono">{{ r.path }}</code>
                  <span class="hint">status</span><span>{{ r.status }}</span>
                  <span class="hint">ip</span><span>{{ r.ip || '—' }}</span>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="!rows.length && !loading">
            <td colspan="4" class="hint">{{ t('common.none') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.pick { cursor: pointer; }
.pick:hover { background: var(--brand-100); }
tr.detail td { background: var(--bg); }
.detail-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: .2rem .8rem;
  font-size: .85rem;
  padding: .3rem 0;
}
</style>
