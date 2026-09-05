import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The API sits behind the same nginx that fronts the stack. In dev, Vite
// proxies these prefixes so the app makes the same relative calls in dev
// and production, with no base URL switch and no CORS.
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
