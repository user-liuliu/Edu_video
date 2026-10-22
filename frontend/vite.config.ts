import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // 开发时把 /api 转发给 FastAPI 后端
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: false },
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
    server: {
      deps: {
        // Element Plus 的 ES 版本 `import AsyncValidator from 'async-validator'`（CJS 包）。
        // 交给 Node 原生 ESM 加载时拿到的是模块对象而不是类，表单校验会静默通过；
        // 让 Vitest 转换 Element Plus，按打包器的方式处理默认导出（浏览器构建本来就没有这个问题）
        inline: ['element-plus'],
      },
    },
  },
})
