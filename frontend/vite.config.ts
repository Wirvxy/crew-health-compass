import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
// Dev only: forward API calls to the local FastAPI server, so the browser talks to one origin (no CORS).
// Production must route /datasets and /api to the API on the same origin, or set VITE_API_BASE_URL.
export default defineConfig(({mode}) => {
  const target = loadEnv(mode, '.', '').DATASET_PROXY_TARGET || 'http://127.0.0.1:8000'
  return { plugins: [react()], server: { proxy: { '/datasets': target, '/api': target } } }
})
