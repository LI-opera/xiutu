import { defineConfig } from 'vite';

const apiTarget = process.env.XIUTU_API_TARGET ?? 'http://127.0.0.1:8020';

export default defineConfig({
  server: {
    host: 'localhost',
    port: 5175,
    strictPort: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: false },
    },
  },
  preview: { host: 'localhost', port: 4175, strictPort: true },
  build: { outDir: process.env.XIUTU_BUILD_DIR ?? 'dist' },
});
