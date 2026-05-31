import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Static demo deployed to https://ash1998.github.io/PACT/ — base must match the repo path.
export default defineConfig({
  base: '/PACT/',
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
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
