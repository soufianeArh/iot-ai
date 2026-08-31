import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The API lives behind the nginx that already fronts the stack. In dev the
// browser talks to Vite and Vite forwards these prefixes to it, so the app
// makes the SAME relative calls in dev and in production - no base-URL switch,
// no CORS, and nothing to change at build time.
const API = 'http://localhost'
const proxy = {}
for (const p of ['/api', '/video', '/ai', '/hls', '/whep', '/snapshots']) {
  proxy[p] = { target: API, changeOrigin: true }
}

export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, proxy },
  build: {
    // Built into web/dist, NOT web/html: Vite empties its output directory on
    // every build, which would delete the hand-written pages still in use.
    outDir: '../web/dist',
    emptyOutDir: true,
  },
})
