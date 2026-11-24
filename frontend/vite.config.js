import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // escucha en todas las interfaces (0.0.0.0), no solo localhost
    port: 5174,
    strictPort: true,
    proxy: { '/api': 'http://localhost:8001' },
  },
})
