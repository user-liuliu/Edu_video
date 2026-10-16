<script setup lang="ts">
import type { FormInstance } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { errorText } from '../api/http'
import AuthCard from '../components/AuthCard.vue'
import { decideRoute } from '../router/guards'
import { useAuthStore } from '../stores/auth'
import { loginPasswordRules, usernameRules } from './authRules'

const auth = useAuthStore()
const router = useRouter()

const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '' })
const rules = { username: usernameRules, password: loginPasswordRules }
const submitting = ref(false)
const serverError = ref('')

async function onSubmit() {
  if (submitting.value) return
  serverError.value = ''
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const me = await auth.login(form.username.trim(), form.password)
    // 和路由守卫同一套规则：active 去首页，其他状态去账号状态页
    const target = decideRoute({ name: 'home', meta: {} }, me)
    await router.push(target === true ? { name: 'home' } : target)
  } catch (e) {
    serverError.value = errorText(e)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthCard title="登录">
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      hide-required-asterisk
      @submit.prevent="onSubmit"
    >
      <el-form-item label="用户名" prop="username">
        <el-input v-model="form.username" autocomplete="username" />
      </el-form-item>
      <el-form-item label="密码" prop="password">
        <el-input v-model="form.password" type="password" autocomplete="current-password" />
      </el-form-item>
      <p v-show="serverError" class="form-error" role="alert">{{ serverError }}</p>
      <el-button class="submit" type="primary" native-type="submit" :loading="submitting" :disabled="submitting">
        登录
      </el-button>
    </el-form>
    <template #footer>
      还没有账号？<RouterLink :to="{ name: 'register' }">注册</RouterLink>
    </template>
  </AuthCard>
</template>

<style scoped>
.form-error {
  margin: 0 0 16px;
  padding: 8px 12px;
  border-radius: var(--ev-radius);
  background: var(--el-color-danger-light-9);
  color: var(--ev-color-danger);
}

.submit {
  width: 100%;
  margin-top: 4px;
}
</style>
