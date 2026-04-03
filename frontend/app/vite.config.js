/**
 * Конфигурация Vite.
 *
 * В dev-режиме проксирует /backend → BFF-бэкенд (FastAPI).
 * URL прокси задаётся через VITE_BACKEND_API_PROXY_URL
 * (в Docker: http://backend:8000/api/v1, локально: http://localhost:8000/api/v1).
 */

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(() => {
  const backendProxyUrl = process.env.VITE_BACKEND_API_PROXY_URL || 'http://localhost:8000/api/v1'

  return {
    plugins: [vue(), tailwindcss()],
    resolve: {
      alias: { '@': '/src' },
    },
    server: {
      proxy: {
        '/backend': {
          target: backendProxyUrl,
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/backend/, ''),
        },
      },
    },
  }
})
