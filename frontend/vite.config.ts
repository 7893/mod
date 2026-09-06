import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')

  return {
  // The current dedicated production hostname serves MOD at /. Override only for a deliberate subpath deploy.
  base: env.VITE_BASE_PATH || '/',
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: '127.0.0.1',
    port: 4173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8100',
      },
    },
  },
  build: {
    // 大屏依赖体积大（echarts / 地图 GeoJSON），按库分包，改善首屏加载与浏览器缓存命中。
    // echarts 单库约 625KB 无法再拆，上调警告阈值以消除噪音（它是独立缓存单元，业务改动不影响它）。
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ['echarts', 'vue-echarts'],
          vue: ['vue', 'vue-router', 'pinia'],
          geo: ['china-geojson'],
          icons: ['lucide-vue-next'],
        },
      },
    },
  },
  }
})
