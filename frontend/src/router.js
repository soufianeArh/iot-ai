import { createRouter, createWebHistory } from 'vue-router'

// Lazy-loaded so the initial bundle stays small; chat especially is only
// opened occasionally.
const routes = [
  { path: '/', redirect: '/devices' },
  { path: '/devices', component: () => import('./views/DevicesView.vue') },
  { path: '/cameras', component: () => import('./views/CamerasView.vue') },
  { path: '/detections', component: () => import('./views/DetectionsView.vue') },
  { path: '/alerts', component: () => import('./views/AlertsView.vue') },
  { path: '/ask', component: () => import('./views/AskView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/devices' },
]

// createWebHistory, not hash mode: nginx needs `try_files $uri /index.html`
// or a refresh on /alerts would 404.
export const router = createRouter({ history: createWebHistory(), routes })
