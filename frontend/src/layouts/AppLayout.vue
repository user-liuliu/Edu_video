<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '../api/http'
import { getJob, getOutline } from '../api/outline'
import { useAuthStore } from '../stores/auth'
import { clearAllVideoDraftCache } from '../utils/video-draft-cache'
import { clearPendingOutlineNotifications, outlineNotificationEvent, readPendingOutlineNotifications, removePendingOutlineNotification } from '../utils/outline-job-notification'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const isAdmin = computed(() => auth.user?.role === 'admin')

const teacherNav = [
  { key: 'make', label: '视频制作' },
  { key: 'videos', label: '我的视频' },
  { key: 'drafts', label: '草稿箱' },
  { key: 'memory', label: '我的偏好' },
  { key: 'account', label: '账户设置' },
] as const

const adminNav = [
  { key: 'admin-page-config', label: '页面配置' },
  { key: 'admin-model-config', label: '模型配置' },
  { key: 'admin-users', label: '用户管理' },
] as const

let outlineNotificationTimer: ReturnType<typeof setTimeout> | undefined
let outlineNotificationDisposed = false
let outlineNotificationPolling = false
let outlineCompletionMessages: string[] = []
let outlineCompletionMessageShowing = false
let outlineCompletionReminder: ReturnType<typeof ElMessage.success> | undefined

function showNextOutlineCompletionMessage() {
  if (outlineNotificationDisposed || outlineCompletionMessageShowing || outlineCompletionMessages.length === 0) return
  outlineCompletionMessageShowing = true
  let closed = false
  outlineCompletionReminder = ElMessage.success({
    message: outlineCompletionMessages.shift() as string,
    duration: 3000,
    showClose: false,
    grouping: false,
    onClose: () => {
      if (closed) return
      closed = true
      outlineCompletionReminder = undefined
      void nextTick(() => {
        outlineCompletionMessageShowing = false
        showNextOutlineCompletionMessage()
      })
    },
  })
}

function scheduleOutlineNotificationPoll() {
  clearTimeout(outlineNotificationTimer)
  if (!outlineNotificationDisposed) outlineNotificationTimer = setTimeout(() => { void pollOutlineNotification() }, 1000)
}

async function pollOutlineNotification() {
  if (outlineNotificationDisposed || outlineNotificationPolling) return
  const pending = readPendingOutlineNotifications()
  if (pending.length === 0) {
    showNextOutlineCompletionMessage()
    return
  }
  outlineNotificationPolling = true
  try {
    let shouldRetry = false
    const results = await Promise.all(pending.map(async item => {
      try { return {item, job: await getJob(item.jobId)} }
      catch { shouldRetry = true; return null }
    }))
    const ordered = results.filter((result): result is NonNullable<typeof result> => result !== null)
      .sort((a, b) => (Date.parse(a.job.updated_at ?? '') || 0) - (Date.parse(b.job.updated_at ?? '') || 0))
    for (const {item, job} of ordered) {
      try {
        if (job.id !== item.jobId || job.kind !== 'generate' || ['failed', 'cancelled'].includes(job.status)) {
          removePendingOutlineNotification(item.jobId)
        } else if (job.status === 'succeeded') {
          const outline = await getOutline(item.projectId)
          removePendingOutlineNotification(item.jobId)
          outlineCompletionMessages.push(`${outline.title ?? '项目'}的视频大纲已经生成完毕`)
        } else {
          shouldRetry = true
        }
      } catch {
        shouldRetry = true
      }
    }
    showNextOutlineCompletionMessage()
    if (shouldRetry || readPendingOutlineNotifications().length > 0) scheduleOutlineNotificationPoll()
  } catch {
    scheduleOutlineNotificationPoll()
  } finally {
    outlineNotificationPolling = false
  }
}

function handleOutlineNotificationPending() {
  clearTimeout(outlineNotificationTimer)
  void pollOutlineNotification()
}

const activeTeacherKey = computed(() => {
  if (['project-create', 'project-edit', 'project-outline'].includes(String(route.name))) return 'make'
  if (route.name === 'project-drafts') return 'drafts'
  if (route.name === 'preferences') return 'memory'
  return String(route.query.section ?? 'videos')
})
function teacherTarget(key:string) {
  if(key==='make')return {name:'project-create'}
  if(key==='videos')return {name:'project-list'}
  if(key==='drafts')return {name:'project-drafts'}
  if(key==='memory')return {name:'preferences'}
  return {name:'home',query:{section:key}}
}

async function onLogout() {
  try {
    await auth.logout()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '退出失败，请重试')
    return
  }
  await router.push({ name: 'login' })
  await clearAllVideoDraftCache()
  clearPendingOutlineNotifications()
  outlineCompletionMessages = []
}

onMounted(() => {
  window.addEventListener(outlineNotificationEvent, handleOutlineNotificationPending)
  void pollOutlineNotification()
})

onBeforeUnmount(() => {
  outlineNotificationDisposed = true
  clearTimeout(outlineNotificationTimer)
  outlineCompletionMessages = []
  outlineCompletionReminder?.close()
  window.removeEventListener(outlineNotificationEvent, handleOutlineNotificationPending)
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header app-header--sticky">
      <RouterLink :to="isAdmin ? { name: 'admin-page-config' } : { name: 'home', query: { section: 'videos' } }" class="brand">教学视频助手</RouterLink>
      <nav class="app-nav" aria-label="账号">
        <span v-if="auth.user" class="username">{{ auth.user.username }}</span>
        <RouterLink v-if="isAdmin" :to="{ name: 'admin' }" class="nav-link">管理后台</RouterLink>
        <el-button text @click="onLogout">退出</el-button>
      </nav>
    </header>

    <div class="app-body">
      <aside v-if="isAdmin" class="side-rail side-rail--sticky" aria-label="管理员导航">
        <p class="rail-caption">管理员后台</p>
        <RouterLink
          v-for="item in adminNav"
          :key="item.key"
          :to="{ name: item.key }"
          class="rail-link"
          :class="{ active: route.name === item.key }"
        >
          {{ item.label }}
        </RouterLink>
      </aside>
      <aside v-else class="side-rail side-rail--sticky" aria-label="教师导航">
        <p class="rail-caption">教师工作台</p>
        <RouterLink
          v-for="item in teacherNav"
          :key="item.key"
          :to="teacherTarget(item.key)"
          class="rail-link"
          :class="{ active: activeTeacherKey === item.key }"
        >
          {{ item.label }}
        </RouterLink>
      </aside>

      <main id="main-content" class="app-main">
        <RouterView :key="route.path" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell { min-height: 100vh; background: var(--ev-color-bg); }
.app-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 64px; padding: 0 28px; border-bottom: 1px solid var(--ev-color-border); background: var(--ev-color-surface); }
.brand { color: var(--ev-color-rail); font-family: var(--ev-font-display); font-size: 21px; font-weight: 700; letter-spacing: .04em; text-decoration: none; white-space: nowrap; }
.app-nav { display: flex; align-items: center; gap: 14px; min-width: 0; }
.username { overflow: hidden; color: var(--ev-color-muted); text-overflow: ellipsis; white-space: nowrap; }
.nav-link { color: var(--ev-color-primary-dark); font-size: 14px; text-decoration: none; }
.nav-link:hover { color: var(--ev-color-primary); }
.app-body { display: flex; min-height: calc(100vh - 64px); }
.side-rail { width: 210px; flex: 0 0 210px; padding: 24px 14px; background: var(--ev-color-rail); }
.app-header--sticky { position: sticky; top: 0; z-index: 20; }
.side-rail--sticky { position: sticky; top: 64px; align-self: flex-start; height: calc(100vh - 64px); overflow-y: auto; }
.rail-caption { margin: 0 9px 17px; color: rgba(255, 255, 255, .58); font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.rail-link { display: block; margin: 4px 0; border-radius: var(--ev-radius); padding: 10px 11px; color: rgba(255, 255, 255, .76); font-size: 14px; text-decoration: none; }
.rail-link:hover, .rail-link.active { background: rgba(255, 255, 255, .14); color: #fff; }
.app-main { flex: 1; min-width: 0; width: 100%; max-width: none; padding: 32px 34px 52px; }

@media (max-width: 720px) {
  .app-header { min-height: 58px; padding: 0 16px; }
  .app-header--sticky { top: 0; }
  .brand { font-size: 18px; }
  .app-nav { gap: 7px; font-size: 13px; }
  .app-body { display: block; }
  .side-rail { width: 100%; padding: 10px 12px; overflow-x: auto; white-space: nowrap; }
  .side-rail--sticky { position: static; height: auto; overflow-y: visible; }
  .rail-caption { display: inline-block; margin: 0 9px 0 0; }
  .rail-link { display: inline-block; margin: 0 2px; padding: 8px 10px; font-size: 13px; }
  .app-main { padding: 22px 16px 40px; }
}
</style>
