/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // The dev server runs in Docker behind Caddy (http://localhost:8080).
    host: true,
    port: 5173,
    strictPort: true,
    allowedHosts: ['frontend', 'localhost'],
    // File events do not cross the Windows -> Linux bind mount: poll instead.
    watch: { usePolling: true, interval: 300 },
    hmr: { clientPort: 8080 },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
  },
})
