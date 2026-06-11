import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  root: resolve('./'),
  base: '/static/',
  server: {
    host: 'localhost',
    port: 5173,
    origin: 'http://localhost:5173',
    cors: true,
  },
  build: {
    outDir: resolve('./dist'),
    manifest: true,
    rollupOptions: {
      input: {
        main: resolve('./src/main.js'),
      },
    },
  },
  resolve: {
    alias: {
      '@': resolve('./src'),
    },
  },
})
