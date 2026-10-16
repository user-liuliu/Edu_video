<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { CurrentUser } from '../api/auth'
import { errorText } from '../api/http'
import AuthCard from '../components/AuthCard.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

// active 账号会被路由守卫送回首页，这里只处理另外三种状态
const MESSAGES: Record<Exclude<CurrentUser['status'], 'active'>, string> = {
  pending: '账号正在等待管理员审核',
  rejected: '注册申请未通过',
  disabled: '账号已被停用',
}

const status = computed(() => auth.user?.status)
const message = computed(() => (status.value && status.value !== 'active' ? MESSAGES[status.value] : ''))

const loggingOut = ref(false)
const logoutError = ref('')

async function onLogout() {
  if (loggingOut.value) return
  logoutError.value = ''
  loggingOut.value = true
  try {
    await auth.logout()
    await router.push({ name: 'login' })
  } catch (e) {
    logoutError.value = errorText(e)
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <AuthCard title="账号状态">
    <p v-if="auth.user" class="account">当前账号：{{ auth.user.username }}</p>
    <p class="message" :class="status">{{ message }}</p>
    <p class="contact">如有疑问请联系管理员</p>
    <p v-show="logoutError" class="form-error" role="alert">{{ logoutError }}</p>
    <el-button :loading="loggingOut" :disabled="loggingOut" @click="onLogout">退出登录</el-button>
  </AuthCard>
</template>

<style scoped>
.account {
  margin: 0 0 12px;
  color: var(--ev-color-muted);
  overflow-wrap: anywhere;
}

/* 状态说明：左侧一道竖线，像批改时在作业本页边做的记号 */
.message {
  margin: 0 0 8px;
  padding: 8px 12px;
  border-left: 3px solid var(--ev-color-primary);
  background: var(--el-color-primary-light-9);
  font-size: 17px;
  font-weight: 600;
}

.message.rejected,
.message.disabled {
  border-left-color: var(--ev-color-danger);
  background: var(--el-color-danger-light-9);
}

.contact {
  margin: 0 0 24px;
  color: var(--ev-color-muted);
}

.form-error {
  margin: 0 0 16px;
  padding: 8px 12px;
  border-radius: var(--ev-radius);
  background: var(--el-color-danger-light-9);
  color: var(--ev-color-danger);
}
</style>
