import { createRouter, createWebHistory } from 'vue-router'

// Lazy-loaded: the chat view in particular is only wanted occasionally, and
// this keeps the first paint small.
const routes = [
  { path: '/', redirect: '/devices' },
  { path: '/devices', component: () => import('./views/DevicesView.vue') },
  { path: '/cameras', component: () => import('./views/CamerasView.vue') },
  { path: '/detections', component: () => import('./views/DetectionsView.vue') },
  { path: '/alerts', component: () => import('./views/AlertsView.vue') },
  { path: '/ask', component: () => import('./views/AskView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/devices' },
]

// createWebHistory, not hash mode - which is why nginx needs
// `try_files $uri /index.html`, or a refresh on /alerts 404s.
export const router = createRouter({ history: createWebHistory(), routes })
