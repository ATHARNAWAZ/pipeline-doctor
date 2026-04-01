import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // REST endpoints — proxy directly to backend (no prefix stripping needed)
      '/analyze': { target: 'http://localhost:8000', changeOrigin: true },
      '/lineage': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
      // WebSocket: /ws/query/stream → backend /query/stream
      '/ws': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/ws/, ''),
      },
    },
  },
})
