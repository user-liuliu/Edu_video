<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '../../stores/auth'
import type { UserGender, CurrentUser } from '../../api/auth'
import { getProfile, removeAvatar, updateProfile, uploadAvatar } from '../../api/account'
import { errorText } from '../../api/http'
import UserAvatar from '../../components/UserAvatar.vue'

const auth = useAuthStore()
const loaded = ref(false)
const loading = ref(true), saving = ref(false), avatarBusy = ref(false)
const error = ref(''), success = ref(''), avatarError = ref(''), avatarSuccess = ref('')
const form = reactive({ display_name: '', gender: 'unspecified' as UserGender, school: '' })
const fileInput = ref<HTMLInputElement>()
const selectedFile = ref<File>(), previewUrl = ref('')
const avatarSrc = computed(() => previewUrl.value || auth.avatarUrl)
function applyProfile(user: CurrentUser) {
  auth.user = user
  form.display_name = user.display_name ?? ''
  form.gender = user.gender ?? 'unspecified'
  form.school = user.school ?? ''
}
async function load() {
  loading.value = true
  error.value = ''
  loaded.value = false
  try { applyProfile(await getProfile()); loaded.value = true }
  catch (e) { error.value = errorText(e) }
  finally { loading.value = false }
}
async function save() {
  if (saving.value || loading.value || !loaded.value) return
  saving.value = true
  error.value = ''; success.value = ''
  try {
    applyProfile(await updateProfile({ display_name: form.display_name.trim() || null, gender: form.gender, school: form.school.trim() || null }))
    success.value = '资料已保存'
  } catch (e) { error.value = errorText(e) }
  finally { saving.value = false }
}
function cancelAvatar() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  selectedFile.value = undefined
  if (fileInput.value) fileInput.value.value = ''
}
function selectAvatar(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  cancelAvatar()
  avatarError.value = ''; avatarSuccess.value = ''
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { avatarError.value = '头像仅支持 JPG、PNG 或 WebP 格式'; return }
  if (file.size > 2 * 1024 * 1024) { avatarError.value = '头像不能超过 2 MiB'; return }
  selectedFile.value = file
  previewUrl.value = URL.createObjectURL(file)
}
async function saveAvatar() {
  if (!selectedFile.value || avatarBusy.value) return
  avatarBusy.value = true; avatarError.value = ''; avatarSuccess.value = ''
  try {
    const user = await uploadAvatar(selectedFile.value)
    // Preserve unsaved personal details while updating the shared avatar.
    if (auth.user) auth.user.avatar_url = user.avatar_url
    auth.refreshAvatar()
    cancelAvatar()
    avatarSuccess.value = '头像已保存'
  } catch (e) { avatarError.value = errorText(e) }
  finally { avatarBusy.value = false }
}
async function resetAvatar() {
  if (avatarBusy.value) return
  avatarBusy.value = true; avatarError.value = ''; avatarSuccess.value = ''
  try {
    await removeAvatar()
    if (auth.user) auth.user.avatar_url = null
    auth.refreshAvatar()
    cancelAvatar()
    avatarSuccess.value = '已恢复默认头像'
  } catch (e) { avatarError.value = errorText(e) }
  finally { avatarBusy.value = false }
}
onMounted(load)
onBeforeUnmount(cancelAvatar)
</script>

<template>
  <div class="profile-settings">
    <h2>个人资料</h2>
    <p class="section-description">让你的教学工作区更有个人风格。</p>
    <div class="avatar-editor">
      <UserAvatar :src="avatarSrc" />
      <div>
        <div class="avatar-actions">
          <el-button :disabled="avatarBusy || loading" @click="fileInput?.click()">更换头像</el-button>
          <el-button v-if="auth.user?.avatar_url" text :disabled="avatarBusy || loading" @click="resetAvatar">恢复默认</el-button>
          <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" aria-label="选择头像图片" class="sr-only" :disabled="avatarBusy || loading" @change="selectAvatar" />
        </div>
        <p class="field-hint">支持 JPG、PNG、WebP，大小不超过 2 MiB。</p>
        <div v-if="selectedFile" class="avatar-pending">
          <span>新头像预览，保存后生效</span>
          <el-button size="small" type="primary" :loading="avatarBusy" @click="saveAvatar">保存头像</el-button>
          <el-button size="small" :disabled="avatarBusy" @click="cancelAvatar">取消</el-button>
        </div>
      </div>
    </div>
    <p v-if="avatarError" class="form-error" role="alert">{{ avatarError }}</p>
    <p v-if="avatarSuccess" class="form-success" role="status">{{ avatarSuccess }}</p>
    <el-form class="profile-form" label-position="top" :model="form" :disabled="loading || saving || !loaded" @submit.prevent="save">
      <div class="profile-fields">
        <el-form-item label="显示名称" for="profile-display-name">
          <el-input id="profile-display-name" v-model="form.display_name" maxlength="40" autocomplete="nickname" :placeholder="auth.user?.username" />
        </el-form-item>
        <el-form-item label="登录用户名" for="profile-username">
          <el-input id="profile-username" :model-value="auth.user?.username" readonly autocomplete="username" />
          <p class="field-hint">用户名用于登录，暂不支持修改。</p>
        </el-form-item>
        <el-form-item label="性别" for="profile-gender">
          <el-select id="profile-gender" v-model="form.gender">
            <el-option label="未设置" value="unspecified" /><el-option label="男" value="male" />
            <el-option label="女" value="female" /><el-option label="不愿透露" value="undisclosed" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属学校" for="profile-school">
          <el-input id="profile-school" v-model="form.school" maxlength="100" autocomplete="organization" placeholder="填写你任教的学校（选填）" />
        </el-form-item>
      </div>
      <p v-if="error" class="form-error" role="alert">{{ error }} <el-button text :disabled="saving" @click="load">重新加载</el-button></p>
      <p v-if="success" class="form-success" role="status">{{ success }}</p>
      <div class="form-actions"><el-button type="primary" native-type="submit" :loading="saving || loading" :disabled="!loaded">保存资料</el-button><span class="field-hint">资料仅用于个人账户展示。</span></div>
    </el-form>
  </div>
</template>

<style scoped>
.avatar-editor{display:flex;align-items:center;gap:20px;margin:26px 0 30px}.avatar-actions{display:flex;align-items:center;gap:6px}.avatar-actions .el-button+.el-button{margin-left:0}.avatar-editor .field-hint{margin:8px 0 0}.avatar-pending{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:12px;font-size:12px;color:var(--ev-color-muted)}.avatar-pending .el-button+.el-button{margin-left:0}.profile-form{max-width:760px}.profile-fields{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0 28px}.profile-fields .el-select{width:100%}.profile-fields .field-hint{margin:7px 0 0}.profile-fields :deep(input[readonly]){color:var(--ev-color-muted)}.profile-fields :deep(.el-input__wrapper:has(input[readonly])){background:var(--ev-color-surface-muted)}@media(max-width:600px){.profile-fields{grid-template-columns:1fr}.avatar-editor{gap:14px;align-items:flex-start}.avatar-pending>span{flex-basis:100%}}
</style>
