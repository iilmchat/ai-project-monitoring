import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    ...(mode === 'analyze'
      ? [
          visualizer({
            filename: 'dist/stats.html',
            gzipSize: true,
            template: 'treemap',
          }),
        ]
      : []),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // The project targets ES2023 browsers, so the modulepreload polyfill is
    // unnecessary weight in the entry chunk.
    modulePreload: { polyfill: false },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    css: false,
  },
}))
