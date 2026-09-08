import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// App code calls relative paths (/market/prices); the proxy forwards them to
// the FastAPI backend so there is no hardcoded host in the client.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/market': 'http://localhost:8000',
      '/portfolio': 'http://localhost:8000',
    },
  },
})
