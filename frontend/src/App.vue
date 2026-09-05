<script setup>
import { useI18n } from 'vue-i18n'
import { LOCALES, setLocale } from './i18n'

const { t, locale } = useI18n()

function onLocaleChange(event) {
  setLocale(event.target.value)
}
</script>

<template>
  <header class="topbar">
    <div class="brand">
      {{ t('app.name') }}<small>{{ t('app.tagline') }}</small>
    </div>

    <nav>
      <RouterLink to="/devices">{{ t('nav.devices') }}</RouterLink>
      <RouterLink to="/cameras">{{ t('nav.cameras') }}</RouterLink>
      <RouterLink to="/detections">{{ t('nav.detections') }}</RouterLink>
      <RouterLink to="/alerts">{{ t('nav.alerts') }}</RouterLink>
      <RouterLink to="/ask">{{ t('nav.ask') }}</RouterLink>
    </nav>

    <!-- margin-inline-start:auto keeps this at the trailing edge either way. -->
    <div class="spacer"></div>

    <label class="lang">
      <span class="visually-hidden">{{ t('app.language') }}</span>
      <select :value="locale" @change="onLocaleChange">
        <option v-for="l in LOCALES" :key="l.code" :value="l.code">{{ l.label }}</option>
      </select>
    </label>
  </header>

  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.lang select {
  width: auto;
  background: rgba(255, 255, 255, .12);
  color: #fff;
  border-color: rgba(255, 255, 255, .25);
}
.lang select option { color: #16202c; }

.visually-hidden {
  position: absolute;
  width: 1px; height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
