import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
// Dev only; production must route /datasets to the API on the same origin.
export default defineConfig(({mode}) => ({ plugins: [react()], server: { proxy: { '/datasets': loadEnv(mode, '.', '').DATASET_PROXY_TARGET || 'http://127.0.0.1:8000' } } }))
