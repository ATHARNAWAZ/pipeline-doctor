import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // REST endpoints: /api/analyze, /api/lineage, /api/query/ask, /api/health
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // WebSocket endpoint: proxied separately so Vite upgrades the connection
      '/ws': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/ws/, ''),
      },
    },
  },
})
