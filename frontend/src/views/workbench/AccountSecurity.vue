<script setup lang="ts">
import { nextTick, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { changePassword } from '../../api/account'
import { ApiError, errorText } from '../../api/http'
import { confirmRules, passwordRules, PASSWORD_HINT } from '../authRules'
const formRef = ref<FormInstance>()
const form = reactive({ current: '', password: '', confirm: '' })
const busy = ref(false), error = ref(''), currentError = ref(''), success = ref('')
const rules: FormRules = {
  current: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  password: passwordRules,
  confirm: confirmRules(() => form.password),
}
async function save() {
  if (busy.value) return
  error.value = ''; currentError.value = ''; success.value = ''
  if (!await formRef.value?.validate().catch(() => false)) return
  busy.value = true
  try {
    await changePassword(form.current, form.password)
    form.current = ''; form.password = ''; form.confirm = ''
    await nextTick()
    formRef.value?.clearValidate()
    success.value = '密码已修改，其他设备需要重新登录。'
  } catch (e) {
    if (e instanceof ApiError && e.code === 'invalid_current_password') currentError.value = errorText(e)
    else error.value = errorText(e)
  } finally { busy.value = false }
}
</script>
<template>
  <div class="security-settings">
    <h2>修改密码</h2>
    <p class="section-description">先验证原密码，再设置新密码。修改成功后，其他设备需要重新登录。</p>
    <el-form ref="formRef" class="password-form" :model="form" :rules="rules" label-position="top" :disabled="busy" @submit.prevent="save">
      <el-form-item label="原密码" prop="current" for="current-password" :error="currentError">
        <el-input id="current-password" v-model="form.current" type="password" show-password autocomplete="current-password" @input="currentError = ''" />
      </el-form-item>
      <el-form-item label="新密码" prop="password" for="new-password">
        <el-input id="new-password" v-model="form.password" type="password" show-password autocomplete="new-password" :placeholder="PASSWORD_HINT" />
      </el-form-item>
      <el-form-item label="确认新密码" prop="confirm" for="confirm-password">
        <el-input id="confirm-password" v-model="form.confirm" type="password" show-password autocomplete="new-password" placeholder="再次输入新密码" />
      </el-form-item>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <p v-if="success" class="form-success" role="status">{{ success }}</p>
      <div class="form-actions"><el-button type="primary" native-type="submit" :loading="busy">修改密码</el-button></div>
    </el-form>
  </div>
</template>
<style scoped>.password-form{max-width:420px;margin-top:28px}</style>
