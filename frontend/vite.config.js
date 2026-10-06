import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import process from 'node:process'

const apiTarget = process.env.DOCUMIND_API_TARGET || 'http://127.0.0.1:8000'
const backendPrefixes = ['/auth', '/documents', '/analytics', '/health']

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(backendPrefixes.map((prefix) => [prefix, apiTarget])),
  },
})
