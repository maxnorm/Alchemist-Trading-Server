import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    watch: {
      usePolling: true,
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Split React Query into its own chunk
          'react-query': ['@tanstack/react-query'],
          // Split React Router
          'react-router': ['react-router-dom'],
          // Split chart libraries (large dependencies)
          'charts': ['recharts', 'lightweight-charts'],
          // Split UI libraries
          'ui': ['lucide-react', 'react-hot-toast'],
          // Split form libraries
          'forms': ['react-hook-form', 'zod'],
        },
      },
    },
    // Increase chunk size warning limit since we're manually chunking
    chunkSizeWarningLimit: 600,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
  },
})
