import { createRouter, createWebHistory } from 'vue-router'
import { session, isAdmin } from './auth'

// Lazy-loaded so the initial bundle stays small; chat especially is only
// opened occasionally.
const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
  { path: '/profile', component: () => import('./views/ProfileView.vue') },
  { path: '/users', component: () => import('./views/UsersView.vue'), meta: { adminOnly: true } },
  { path: '/dashboard', component: () => import('./views/DashboardView.vue') },
  { path: '/devices', component: () => import('./views/DevicesView.vue') },
  { path: '/zones', component: () => import('./views/ZonesView.vue'), meta: { adminOnly: true } },
  { path: '/cameras', component: () => import('./views/CamerasView.vue') },
  { path: '/detections', component: () => import('./views/DetectionsView.vue') },
  { path: '/alerts', component: () => import('./views/AlertsView.vue') },
  { path: '/ask', component: () => import('./views/AskView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

// createWebHistory, not hash mode: nginx needs `try_files $uri /index.html`
// or a refresh on /alerts would 404.
export const router = createRouter({ history: createWebHistory(), routes })

// Every route needs a session except /login itself, bounced back with
// ?redirect= so login lands on whatever page was actually requested. The
// backend is still the real gate, this only saves a round trip to find out.
router.beforeEach((to) => {
  const authed = !!session.value
  if (!to.meta.public && !authed) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && authed) {
    return '/dashboard'
  }
  // Same reasoning: the nav link is hidden for non-admins anyway, this just
  // covers someone typing the URL directly. /api/auth/users itself is the
  // real gate.
  if (to.meta.adminOnly && !isAdmin.value) {
    return '/dashboard'
  }
  return true
})
