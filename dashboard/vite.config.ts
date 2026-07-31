import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { simulatorControlPlugin } from './vite-simulator-plugin';

export default defineConfig({
  plugins: [react(), simulatorControlPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
