/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API runs separately (uv run python scripts/serve.py); proxy it in dev.
export default defineConfig({
  plugins: [react()],
  // three.js + react-three-fiber are ~1.2 MB minified; one chunk is fine for a local app.
  build: { chunkSizeWarningLimit: 1500 },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'node',
  },
})
