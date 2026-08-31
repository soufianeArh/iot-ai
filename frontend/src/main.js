import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { i18n, setLocale } from './i18n'
import './styles/theme.css'

// Applies dir and lang to <html> before the first paint, so an Arabic reload
// does not flash left-to-right.
setLocale(i18n.global.locale.value)

createApp(App).use(router).use(i18n).mount('#app')
