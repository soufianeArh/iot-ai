import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { i18n, setLocale } from './i18n'
import './styles/theme.css'

// Set dir/lang before first paint so an Arabic reload doesn't flash LTR.
setLocale(i18n.global.locale.value)

createApp(App).use(router).use(i18n).mount('#app')
