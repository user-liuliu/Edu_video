<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '../api/http'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.user?.role === 'admin')

async function onLogout() {
  try {
    await auth.logout()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '退出失败，请重试')
    return
  }
  await router.push({ name: 'login' })
}
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink :to="{ name: 'home' }" class="brand">教学视频助手</RouterLink>
      <nav class="app-nav" aria-label="账号">
        <span v-if="auth.user" class="username">{{ auth.user.username }}</span>
        <RouterLink v-if="isAdmin" :to="{ name: 'admin' }" class="nav-link">管理后台</RouterLink>
        <el-button text @click="onLogout">退出</el-button>
      </nav>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 24px;
  height: 60px;
  background: var(--ev-color-surface);
  border-bottom: 1px solid var(--ev-color-border);
  /* 顶栏底边一道黑板绿，作为全站唯一的色块 */
  box-shadow: inset 0 -3px 0 var(--ev-color-primary);
}

.brand {
  font-family: var(--ev-font-display);
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--ev-color-primary);
  text-decoration: none;
  white-space: nowrap;
}

.app-nav {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.username {
  color: var(--ev-color-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-link {
  color: var(--ev-color-text);
  text-decoration: none;
}

.nav-link:hover,
.nav-link.router-link-active {
  color: var(--ev-color-primary);
  text-decoration: underline;
  text-underline-offset: 4px;
}

.app-main {
  flex: 1;
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding: 32px 24px 48px;
}

@media (max-width: 600px) {
  .app-header {
    padding: 0 16px;
  }

  .app-nav {
    gap: 8px;
  }

  .app-main {
    padding: 24px 16px 40px;
  }
}
</style>
