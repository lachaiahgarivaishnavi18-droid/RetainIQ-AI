import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({ plugins: [react(), tailwindcss()], server: { port:5174, strictPort:true, proxy: { '/api': 'http://127.0.0.1:8000' } }, build:{rollupOptions:{output:{manualChunks:{charts:['recharts'],react:['react','react-dom','react-router-dom']}}}}, test: { environment: 'jsdom', setupFiles: './src/test-setup.ts', exclude:['e2e/**','node_modules/**'] } })
