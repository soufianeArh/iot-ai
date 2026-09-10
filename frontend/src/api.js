// Talks to the backend. Paths are relative: Vite proxies them in dev, and
// nginx serves this app plus the APIs from the same origin in prod, so
// there's no base URL to configure and no CORS.

import { getToken, clearSession } from './auth'

function authHeaders(extra) {
  const token = getToken()
  return { ...extra, ...(token ? { Authorization: `Bearer ${token}` } : {}) }
}

// A dead or missing token looks the same everywhere: send back to /login.
// Hard redirect rather than the router, api.js has no router of its own and
// a full reload is fine for what should be a rare event.
function handleUnauthorized() {
  clearSession()
  if (location.pathname !== '/login') {
    location.href = `/login?redirect=${encodeURIComponent(location.pathname)}`
  }
}

async function request(url, options = {}) {
  const res = await fetch(url, { ...options, headers: authHeaders(options.headers) })

  if (res.status === 401) {
    handleUnauthorized()
    throw new Error('session expired, please sign in again')
  }

  const type = res.headers.get('content-type') || ''
  if (!type.includes('application/json')) {
    // Usually nginx's own HTML error page when a backend service is down.
    throw new Error(`${res.status} - service unavailable (expected JSON)`)
  }

  const body = await res.json()
  if (!res.ok) throw new Error(body.message || body.error || `HTTP ${res.status}`)
  return body
}

const get = (url) => request(url)
const send = (method) => (url, body) =>
  request(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })

const post = send('POST')
const put = send('PUT')

async function del(url) {
  const res = await fetch(url, { method: 'DELETE', headers: authHeaders() })
  if (res.status === 401) {
    handleUnauthorized()
    throw new Error('session expired, please sign in again')
  }
  if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`)
}

export const api = {
  // auth. login sends no token of its own, there isn't one yet.
  login: (username, password) => post('/api/auth/login', { username, password }),
  logout: () => post('/api/auth/logout'),
  me: () => get('/api/auth/me'),
  updateProfile: (body) => put('/api/auth/me', body),

  // user management, ADMIN only, enforced server side
  users: () => get('/api/auth/users'),
  addUser: (body) => post('/api/auth/users', body),
  updateUser: (id, body) => put(`/api/auth/users/${id}`, body),
  deleteUser: (id) => del(`/api/auth/users/${id}`),

  // audit log, ADMIN only. Every service ships its mutations here.
  audit: (params) => get(`/api/auth/audit?${new URLSearchParams(params)}`),

  // devices
  devices: () => get('/api/devices'),
  addDevice: (body) => post('/api/devices', body),
  updateDevice: (id, body) => put(`/api/devices/${id}`, body),
  deleteDevice: (id) => del(`/api/devices/${id}`),

  // zones, a device belongs to at most one. Reading is open to any role,
  // create/rename/delete is ADMIN only (enforced server side).
  zones: () => get('/api/zones'),
  addZone: (body) => post('/api/zones', body),
  updateZone: (id, body) => put(`/api/zones/${id}`, body),
  deleteZone: (id) => del(`/api/zones/${id}`),
  deviceProperties: (id) => get(`/api/devices/${id}/properties`),
  // Same endpoint: with `key` it returns that property's history, newest
  // first, instead of the latest value of every property.
  deviceHistory: (id, key, limit = 200) =>
    get(`/api/devices/${id}/properties?key=${encodeURIComponent(key)}&limit=${limit}`),
  // MQTT traffic from a deviceCode/productKey pair nobody registered.
  unregisteredDevices: () => get('/api/devices/unregistered'),

  // cameras
  cameras: () => get('/video/camera'),
  addCamera: (body) => post('/video/camera', body),
  deleteCamera: (id) => del(`/video/camera/${id}`),
  probeCamera: (id) => post(`/video/camera/${id}/probe`),
  streamInfo: (id) => get(`/video/camera/${id}/stream`),
  startStream: (id) => post(`/video/camera/${id}/stream`),
  stopStream: (id) => del(`/video/camera/${id}/stream`),

  // analysis
  tasks: () => get('/ai/tasks'),
  startTask: (id, model) =>
    post(`/ai/tasks/${id}${model ? `?model=${encodeURIComponent(model)}` : ''}`),
  stopTask: (id) => del(`/ai/tasks/${id}`),
  models: () => get('/ai/models'),
  labels: () => get('/ai/labels'),
  detections: (params) => get(`/ai/detections?${new URLSearchParams(params)}`),
  detectionSummary: (minutes) => get(`/ai/detections/summary?minutes=${minutes}`),

  // alerts
  rules: () => get('/ai/rules'),
  addRule: (body) => post('/ai/rules', body),
  updateRule: (id, body) => put(`/ai/rules/${id}`, body),
  deleteRule: (id) => del(`/ai/rules/${id}`),
  alerts: (params) => get(`/ai/alerts?${new URLSearchParams(params)}`),
  alertSummary: () => get('/ai/alerts/summary'),
  // open (unacknowledged) counts + worst severity, grouped by camera and device
  openAlertCounts: () => get('/ai/alerts/open-counts'),
  ackAlert: (id) => post(`/ai/alerts/${id}/ack`),

  // chat
  chat: (message, history) => post('/ai/chat', { message, history }),
  chatTools: () => get('/ai/chat/tools'),
  chatHealth: () => get('/ai/chat/health'),
}
