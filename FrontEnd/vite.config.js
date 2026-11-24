import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      // Same-origin API calls in dev: the HttpOnly refresh cookie just works.
      proxy: { '/api': { target: env.VITE_API_PROXY || 'http://localhost:8000', changeOrigin: true } },
    },
  }
})
