import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';

export default defineConfig({
  plugins: [vue()],
  root: resolve(__dirname, 'frontend'),
  base: '/static/dist/',
  build: {
    outDir: resolve(__dirname, 'webapp/static/static/dist'),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: resolve(__dirname, 'frontend/src/main.js'),
    },
  },
  server: {
    port: 3000,
    strictPort: true,
    cors: true,
    origin: 'http://127.0.0.1:3000',
    hmr: {
      protocol: 'ws',
    },
  },
});
