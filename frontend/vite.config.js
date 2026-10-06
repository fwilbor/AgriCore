import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development, Vite forwards /api/* to FastAPI, so the browser sees one
// origin and no CORS setup is needed. In production, VITE_API_URL points at
// the deployed API (e.g. the Lambda Function URL).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Split big libraries into their own cacheable files.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          mui: ['@mui/material', '@mui/icons-material', '@emotion/react', '@emotion/styled'],
          datagrid: ['@mui/x-data-grid'],
        },
      },
    },
  },
})
