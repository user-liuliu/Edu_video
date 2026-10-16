import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import { setAuthFailureHandler } from './api/http'
import { router } from './router'
import { createAuthFailureHandler } from './router/authFailure'
import './styles/tokens.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
// 使用中会话失效或账号被停用：更新登录状态并跳到登录页 / 账号状态页
setAuthFailureHandler(createAuthFailureHandler(router))
app.mount('#app')
