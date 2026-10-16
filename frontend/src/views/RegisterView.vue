<script setup lang="ts">
import type { FormInstance } from 'element-plus'
import { reactive, ref } from 'vue'
import { errorText } from '../api/http'
import AuthCard from '../components/AuthCard.vue'
import { useAuthStore } from '../stores/auth'
import { confirmRules, passwordRules, usernameRules } from './authRules'

const auth = useAuthStore()

const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '', confirm: '' })
const rules = {
  username: usernameRules,
  password: passwordRules,
  confirm: confirmRules(() => form.password),
}
const submitting = ref(false)
const serverError = ref('')
// 注册成功后换成待审核提示；注册不会登录，所以不跳转
const done = ref(false)

async function onSubmit() {
  if (submitting.value) return
  serverError.value = ''
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await auth.register(form.username.trim(), form.password)
    done.value = true
  } catch (e) {
    serverError.value = errorText(e)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthCard title="注册账号">
    <div v-if="done" class="done" role="status">
      <p class="done-title">注册成功，请等待管理员审核</p>
      <p class="done-hint">审核通过后即可登录使用。</p>
      <RouterLink :to="{ name: 'login' }" class="to-login">去登录</RouterLink>
    </div>
    <el-form
      v-else
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      hide-required-asterisk
      @submit.prevent="onSubmit"
    >
      <el-form-item label="用户名" prop="username">
        <el-input v-model="form.username" autocomplete="username" aria-describedby="username-hint" />
        <p id="username-hint" class="hint">3–32 位，可以用字母、数字、下划线和汉字</p>
      </el-form-item>
      <el-form-item label="密码" prop="password">
        <el-input v-model="form.password" type="password" autocomplete="new-password" aria-describedby="password-hint" />
        <p id="password-hint" class="hint">8–128 位</p>
      </el-form-item>
      <el-form-item label="确认密码" prop="confirm">
        <el-input v-model="form.confirm" type="password" autocomplete="new-password" />
      </el-form-item>
      <p v-show="serverError" class="form-error" role="alert">{{ serverError }}</p>
      <el-button class="submit" type="primary" native-type="submit" :loading="submitting" :disabled="submitting">
        注册
      </el-button>
    </el-form>
    <template v-if="!done" #footer>
      已有账号？<RouterLink :to="{ name: 'login' }">去登录</RouterLink>
    </template>
  </AuthCard>
</template>

<style scoped>
.hint {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ev-color-muted);
}

/* 校验出错时，Element Plus 的错误提示会出现在同一位置，隐藏说明文字避免重叠 */
.el-form-item.is-error .hint {
  display: none;
}

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

.done-title {
  margin: 0 0 4px;
  font-weight: 600;
  color: var(--ev-color-success);
}

.done-hint {
  margin: 0 0 20px;
  color: var(--ev-color-muted);
}

.to-login {
  display: inline-block;
  padding: 6px 20px;
  border-radius: var(--ev-radius);
  background: var(--ev-color-primary);
  color: #fff;
  text-decoration: none;
}

.to-login:hover {
  background: var(--el-color-primary-light-3);
}
</style>
