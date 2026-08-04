import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: process.env.VITE_PROXY_TARGET || process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ready': {
        target: process.env.VITE_PROXY_TARGET || process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/metrics': {
        target: process.env.VITE_PROXY_TARGET || process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('@supabase')) return 'supabase'
          if (id.includes('framer-motion')) return 'motion'
          if (id.includes('lucide-react')) return 'icons'
          if (id.includes('react-dom') || id.includes('react-router') || id.includes('/react/')) return 'react'
          if (id.includes('axios')) return 'http'
          return 'vendor'
        },
      },
    },
  },
})
