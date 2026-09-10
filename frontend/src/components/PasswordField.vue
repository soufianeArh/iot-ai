<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, required: true },
  autocomplete: { type: String, default: 'current-password' },
  required: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const { t } = useI18n()
const visible = ref(false)
const type = computed(() => (visible.value ? 'text' : 'password'))
</script>

<template>
  <label class="field">
    <span>{{ label }}</span>
    <div class="password-wrap">
      <input
        :value="modelValue"
        :type="type"
        class="ltr"
        :autocomplete="autocomplete"
        :required="required"
        @input="emit('update:modelValue', $event.target.value)"
      >
      <button
        type="button"
        class="password-toggle"
        :aria-label="visible ? t('auth.hidePassword') : t('auth.showPassword')"
        :title="visible ? t('auth.hidePassword') : t('auth.showPassword')"
        @click="visible = !visible"
      >
        <!-- open eye: password hidden, click reveals it -->
        <svg v-if="!visible" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
        <!-- slashed eye: password shown, click hides it -->
        <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7a21.6 21.6 0 0 1 5.06-5.94M9.9 4.24A10.94 10.94 0 0 1 12 5c7 0 11 7 11 7a21.6 21.6 0 0 1-2.61 3.55"/>
          <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/>
          <line x1="1" y1="1" x2="23" y2="23"/>
        </svg>
      </button>
    </div>
  </label>
</template>

<style scoped>
.password-wrap { position: relative; }
/* room for the button, on the trailing edge in either direction */
.password-wrap input { padding-inline-end: 2.1rem; }

.password-toggle {
  position: absolute;
  inset-inline-end: .25rem;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  padding: .2rem;
  margin: 0;
  line-height: 0;
  cursor: pointer;
  color: var(--text-dim);
}
.password-toggle:hover { color: var(--text); background: transparent; }
</style>
