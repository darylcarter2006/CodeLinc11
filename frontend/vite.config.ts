/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// Same Content-Security-Policy as customHttp.yml (Amplify), so `npm run preview` catches violations
// before a deploy. connect-src takes the API origin from VITE_API_BASE_URL.
function contentSecurityPolicy(apiBase: string): string {
  const api = apiBase ? new URL(apiBase).origin : ''
  return [
    "default-src 'self'",
    "script-src 'self' https://accounts.google.com/gsi/client",
    // Google's sign-in button sets inline styles when it renders; scripts stay strict.
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com/gsi/style",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://*.googleusercontent.com",
    `connect-src 'self' ${api} https://accounts.google.com/gsi/`,
    'frame-src https://accounts.google.com/gsi/',
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join('; ')
}

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
    preview: {
      headers: {
        'Content-Security-Policy': contentSecurityPolicy(env.VITE_API_BASE_URL ?? ''),
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Cross-Origin-Opener-Policy': 'same-origin-allow-popups',
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
    },
  }
})
