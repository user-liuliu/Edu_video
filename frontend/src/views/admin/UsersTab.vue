<!-- 用户管理：开放注册开关、按状态筛选和用户名搜索、审核 / 停用 / 重置密码 / 设为管理员 -->
<script setup lang="ts">
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import {
  getRegistration,
  listUsers,
  putRegistration,
  resetPassword,
  setRole,
  userAction,
  type UserAction,
  type UserOut,
  type UserRole,
  type UserStatus,
} from '../../api/admin'
import { errorText } from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { PASSWORD_HINT, confirmRules, passwordRules } from '../authRules'

const ROLE_TEXT: Record<UserRole, string> = { teacher: '老师', admin: '管理员' }
const STATUS_TEXT: Record<UserStatus, string> = {
  pending: '待审核',
  active: '正常',
  rejected: '已拒绝',
  disabled: '已停用',
}
// 对自己的账号操作时额外提醒（停用、重置密码会让自己的会话失效）
const SELF_RELOGIN_NOTE = '这是你自己的账号，操作后你需要重新登录'

const auth = useAuthStore()
const isSelf = (u: UserOut) => u.id === auth.user?.id

const STATUS_FILTERS: { value: UserStatus | ''; label: string }[] = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待审核' },
  { value: 'active', label: '正常' },
  { value: 'rejected', label: '已拒绝' },
  { value: 'disabled', label: '已停用' },
]

// ---------- 开放注册 ----------

const registrationOpen = ref(false)
const registrationLoading = ref(false)

async function loadRegistration() {
  try {
    registrationOpen.value = (await getRegistration()).open
  } catch (e) {
    ElMessage.error(errorText(e))
  }
}

async function onRegistrationChange(open: string | number | boolean) {
  const next = Boolean(open)
  registrationLoading.value = true
  try {
    registrationOpen.value = (await putRegistration(next)).open
    ElMessage.success(next ? '已开放注册' : '已关闭注册')
  } catch (e) {
    ElMessage.error(errorText(e))
  } finally {
    registrationLoading.value = false
  }
}

// ---------- 列表 ----------

const filters = reactive({ status: '' as UserStatus | '', q: '' })
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const items = ref<UserOut[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await listUsers({
      ...(filters.status ? { status: filters.status } : {}),
      ...(filters.q.trim() ? { q: filters.q.trim() } : {}),
      page: page.value,
      page_size: pageSize.value,
    })
    // 当前页的人都被处理完（例如筛选"待审核"时全部通过）：退回上一页
    if (res.items.length === 0 && res.total > 0 && page.value > 1) {
      page.value = Math.max(1, Math.ceil(res.total / pageSize.value))
      return load()
    }
    items.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error(errorText(e))
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function onPageSizeChange() {
  page.value = 1
  void load()
}

onMounted(() => {
  void loadRegistration()
  void load()
})

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

// ---------- 操作 ----------

type RowAction =
  | { kind: 'status'; action: UserAction; label: string; danger?: boolean }
  | { kind: 'password'; label: string; danger?: false }
  | { kind: 'role'; role: UserRole; label: string; danger?: boolean }

function actionsFor(u: UserOut): RowAction[] {
  switch (u.status) {
    case 'pending':
      return [
        { kind: 'status', action: 'approve', label: '通过' },
        { kind: 'status', action: 'reject', label: '拒绝', danger: true },
      ]
    case 'rejected':
      return [{ kind: 'status', action: 'approve', label: '通过' }]
    case 'active':
      return [
        { kind: 'status', action: 'disable', label: '停用', danger: true },
        { kind: 'password', label: '重置密码' },
        u.role === 'admin'
          ? { kind: 'role', role: 'teacher', label: '取消管理员', danger: true }
          : { kind: 'role', role: 'admin', label: '设为管理员' },
      ]
    case 'disabled':
      return [
        { kind: 'status', action: 'enable', label: '启用' },
        { kind: 'password', label: '重置密码' },
      ]
  }
}

/** 需要先确认的操作：返回确认框文字；不需要确认返回 null */
function confirmText(a: RowAction, u: UserOut): string | null {
  if (a.kind === 'status' && a.action === 'disable') {
    const self = isSelf(u) ? `${SELF_RELOGIN_NOTE}。` : ''
    return `停用后「${u.username}」将不能再使用系统，已有的视频会保留。${self}确定停用吗？`
  }
  if (a.kind === 'status' && a.action === 'reject') return `确定拒绝「${u.username}」的注册申请吗？`
  if (a.kind === 'role' && a.role === 'teacher') {
    if (isSelf(u)) return '这是你自己的账号，取消后你将失去管理后台权限。确定取消管理员吗？'
    return `取消后「${u.username}」将不能再进入管理后台。确定取消管理员吗？`
  }
  return null
}

const SUCCESS_TEXT: Record<UserAction, string> = {
  approve: '已通过',
  reject: '已拒绝',
  disable: '已停用',
  enable: '已启用',
}

/** 正在处理的用户 id，期间禁用这一行的按钮 */
const busyId = ref<string | null>(null)

async function run(a: RowAction, u: UserOut) {
  if (a.kind === 'password') return openPassword(u)
  if (busyId.value) return

  const text = confirmText(a, u)
  if (text) {
    try {
      await ElMessageBox.confirm(text, a.label, {
        type: 'warning',
        confirmButtonText: a.label,
        cancelButtonText: '取消',
      })
    } catch {
      return // 取消
    }
  }

  busyId.value = u.id
  try {
    if (a.kind === 'status') {
      await userAction(u.id, a.action)
      ElMessage.success(SUCCESS_TEXT[a.action])
    } else {
      await setRole(u.id, a.role)
      ElMessage.success(a.role === 'admin' ? '已设为管理员' : '已取消管理员')
    }
  } catch (e) {
    ElMessage.error(errorText(e))
  } finally {
    busyId.value = null
  }
  // 成功或失败都重新读取，失败时状态可能已被别的管理员改过
  await load()
}

// ---------- 重置密码 ----------

const pwFormRef = ref<FormInstance>()
const pw = reactive({ open: false, user: null as UserOut | null, password: '', confirm: '', saving: false })
const pwRules = { password: passwordRules, confirm: confirmRules(() => pw.password) }

function openPassword(u: UserOut) {
  pw.user = u
  pw.password = ''
  pw.confirm = ''
  pw.open = true
  pwFormRef.value?.clearValidate()
}

async function submitPassword() {
  if (!pw.user || pw.saving) return
  const valid = await pwFormRef.value?.validate().catch(() => false)
  if (!valid) return
  pw.saving = true
  try {
    await resetPassword(pw.user.id, pw.password)
    ElMessage.success('密码已重置')
    pw.open = false
  } catch (e) {
    ElMessage.error(errorText(e))
  } finally {
    pw.saving = false
  }
}

function onPasswordClosed() {
  pw.password = ''
  pw.confirm = ''
}
</script>

<template>
  <div class="users">
    <h2 class="sr-only">用户管理</h2>

    <div class="toolbar">
      <div class="registration">
        <span class="registration-label" aria-hidden="true">开放注册</span>
        <el-switch
          :model-value="registrationOpen"
          :loading="registrationLoading"
          aria-label="开放注册"
          @change="onRegistrationChange"
        />
        <span class="ev-muted">{{ registrationOpen ? '新老师可以自行注册，审核通过后使用' : '已关闭，新老师不能注册' }}</span>
      </div>
      <form class="filters" role="search" @submit.prevent="search">
        <el-select v-model="filters.status" aria-label="按状态筛选" class="status-filter" @change="search">
          <el-option v-for="s in STATUS_FILTERS" :key="s.value" :value="s.value" :label="s.label" />
        </el-select>
        <el-input v-model="filters.q" aria-label="搜索用户名" placeholder="搜索用户名" clearable class="search" @clear="search" />
        <el-button native-type="submit">搜索</el-button>
      </form>
    </div>

    <div v-loading="loading" class="ev-table-wrap">
      <table class="ev-table">
        <caption class="sr-only">用户列表</caption>
        <thead>
          <tr>
            <th scope="col">用户名</th>
            <th scope="col">角色</th>
            <th scope="col">状态</th>
            <th scope="col">注册时间</th>
            <th scope="col">视频项目数</th>
            <th scope="col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in items" :key="u.id">
            <th scope="row" class="username">{{ u.username }}</th>
            <td>{{ ROLE_TEXT[u.role] }}</td>
            <td><span :class="['status', `status-${u.status}`]">{{ STATUS_TEXT[u.status] }}</span></td>
            <td class="time">{{ formatTime(u.created_at) }}</td>
            <td>{{ u.video_count ?? 0 }}</td>
            <td class="actions">
              <el-button
                v-for="a in actionsFor(u)"
                :key="a.label"
                size="small"
                :type="a.danger ? 'danger' : undefined"
                :plain="a.danger"
                :disabled="busyId === u.id"
                @click="run(a, u)"
              >
                {{ a.label }}
              </el-button>
            </td>
          </tr>
          <tr v-if="!loading && items.length === 0">
            <td colspan="6" class="empty ev-muted">没有符合条件的用户</td>
          </tr>
        </tbody>
      </table>
    </div>

    <el-pagination
      v-if="total > 0"
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      class="pager"
      @current-change="load"
      @size-change="onPageSizeChange"
    />

    <el-dialog v-model="pw.open" :title="`重置密码：${pw.user?.username ?? ''}`" width="420px" @closed="onPasswordClosed">
      <p v-if="pw.user && isSelf(pw.user)" class="self-note">{{ SELF_RELOGIN_NOTE }}</p>
      <el-form ref="pwFormRef" :model="pw" :rules="pwRules" label-position="top" @submit.prevent="submitPassword">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="pw.password" type="password" autocomplete="new-password" aria-describedby="reset-password-hint" />
          <p id="reset-password-hint" class="ev-muted hint">{{ PASSWORD_HINT }}</p>
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm">
          <el-input v-model="pw.confirm" type="password" autocomplete="new-password" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pw.open = false">取消</el-button>
        <el-button type="primary" :loading="pw.saving" :disabled="pw.saving" @click="submitPassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px 24px;
  margin-bottom: 16px;
}

.registration {
  display: flex;
  align-items: center;
  gap: 10px;
}

.registration-label {
  font-weight: 600;
}

.filters {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-filter {
  width: 120px;
}

.search {
  width: 200px;
}

.username {
  max-width: 240px;
  overflow-wrap: anywhere;
}

.time {
  white-space: nowrap;
}

.actions {
  white-space: nowrap;
}

.status-pending {
  color: var(--ev-color-primary);
  font-weight: 600;
}

.status-active {
  color: var(--ev-color-success);
}

.status-rejected,
.status-disabled {
  color: var(--ev-color-muted);
}

.empty {
  padding: 32px 12px;
  text-align: center;
}

.pager {
  justify-content: flex-end;
  margin-top: 16px;
}

.self-note {
  margin: 0 0 12px;
  color: var(--ev-color-danger);
  font-weight: 600;
}

.hint {
  margin: 4px 0 0;
  line-height: 1.5;
}

.el-form-item.is-error .hint {
  display: none;
}

@media (max-width: 600px) {
  .filters {
    flex-wrap: wrap;
  }

  .search {
    width: 100%;
  }
}
</style>
