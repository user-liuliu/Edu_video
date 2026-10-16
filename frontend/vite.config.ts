import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // 开发时把 /api 转发给 FastAPI 后端
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    // Element Plus 全量注册（app.use(ElementPlus)），单独打成一个约 1 MB 的 chunk，便于浏览器长期缓存；
    // 默认 500 kB 的提示对它没有意义，所以放宽到 1100 kB，应用自身的 chunk 仍然很小
    chunkSizeWarningLimit: 1100,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [{ name: 'element-plus', test: /node_modules[\\/](element-plus|@element-plus)[\\/]/ }],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.spec.ts'],
  },
})
