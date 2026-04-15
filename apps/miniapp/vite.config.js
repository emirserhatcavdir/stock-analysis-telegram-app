import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: true,
    proxy: {
      '/scan': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/rank': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/analysis': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/symbol': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/watchlist': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});