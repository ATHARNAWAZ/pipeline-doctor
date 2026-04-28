import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Necessary to allow external access to the container
    proxy: {
      // Proxy to the 'backend' service name, NOT 'localhost'
      '/analyze': { target: 'http://backend:8000', changeOrigin: true },
      '/lineage': { target: 'http://backend:8000', changeOrigin: true },
      '/health': { target: 'http://backend:8000', changeOrigin: true },
      '/query': { target: 'http://backend:8000', changeOrigin: true },
      
      '/ws': {
        target: 'ws://backend:8000', // Use ws:// for WebSocket targets
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/ws/, ''),
      },
    },
  },
})