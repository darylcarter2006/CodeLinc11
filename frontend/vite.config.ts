import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      // Forward API calls to the local FastAPI server so dev needs no CORS setup.
      proxy: {
        '/v1': env.API_PROXY_TARGET || 'http://localhost:8000',
      },
    },
  }
})
