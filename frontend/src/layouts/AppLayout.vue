<script setup lang="ts">
import AppIcon from '../components/AppIcon.vue'
import UserAvatar from '../components/UserAvatar.vue'
import CreditBalanceLink from '../components/CreditBalanceLink.vue'
import { ElMessage } from 'element-plus'
import {notifyCreditsChanged} from '../api/credits'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { isNavigationFailure, NavigationFailureType, useRoute, useRouter } from 'vue-router'
import { ApiError } from '../api/http'
import { getJob, getOutline } from '../api/outline'
import {getPpt,getPptJob} from '../api/presentations'
import { useAuthStore } from '../stores/auth'
import {clearCreationMemory,creationPath} from '../utils/creation-memory'
import { clearAllVideoDraftCache } from '../utils/video-draft-cache'
import { clearPendingOutlineNotifications, outlineNotificationEvent, readPendingOutlineNotifications, removePendingOutlineNotification } from '../utils/outline-job-notification'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const isAdmin = computed(() => auth.user?.role === 'admin')
const railCollapsed = ref(false)
const creationSession = ref(0)
let startingNewCreation = false
function creationMode(path: string) {
  if (/^[/]projects[/](new|[^/]+[/]edit)$/.test(path)) return 'video' as const
  if (/^[/]presentations[/](new|[^/]+[/]edit)$/.test(path)) return 'ppt' as const
}
function resetCreationSession() {
  clearCreationMemory()
  creationSession.value += 1
}
// Successful navigation runs before the old form unmounts. Its epoch prevents
// the discarded form from writing stale values back into the next session.
const removeCreationNavigation = router.afterEach((to, from, failure) => {
  if (failure) return
  const source = creationMode(from.path), target = creationMode(to.path)
  const continuing = source && target && creationPath(target) === to.fullPath
  if (startingNewCreation || ((source || target) && !continuing)) resetCreationSession()
})
async function startNewCreation(event: MouseEvent) {
  if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  if (startingNewCreation) return
  startingNewCreation = true
  try {
    const failure = await router.push({name: 'project-create'})
    // Re-entering /projects/new is a duplicate navigation; explicitly remount.
    if (isNavigationFailure(failure, NavigationFailureType.duplicated)) resetCreationSession()
  } finally {
    startingNewCreation = false
  }
}

const isCreationPage = computed(() => !isAdmin.value && ['project-create', 'project-edit', 'ppt-create', 'ppt-edit'].includes(String(route.name)))

const teacherNav = [
  { key: 'make', label: '工作台', icon: 'workbench' },
  { key: 'videos', label: '我的作品', icon: 'works' },
  { key: 'drafts', label: '草稿箱', icon: 'drafts' },
  { key: 'account', label: '账户设置', icon: 'account' },
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
      try { return {item, job: await (item.target==='ppt'?getPptJob(item.jobId):getJob(item.jobId))} }
      catch { shouldRetry = true; return null }
    }))
    const ordered = results.filter((result): result is NonNullable<typeof result> => result !== null)
      .sort((a, b) => (Date.parse(a.job.updated_at ?? '') || 0) - (Date.parse(b.job.updated_at ?? '') || 0))
    for (const {item, job} of ordered) {
      try {
        if(item.target==='ppt'&&['render','revise'].includes(job.kind)&&['succeeded','failed','cancelled'].includes(job.status))notifyCreditsChanged()
        if (job.id !== item.jobId || !(item.target==='ppt'?['outline','render','revise']:['generate','video','video_export']).includes(job.kind) || ['failed', 'cancelled'].includes(job.status)) {
          removePendingOutlineNotification(item.jobId)
        } else if (job.status === 'succeeded') {
          if(item.target==='ppt'){
            const project=await getPpt(item.projectId)
            outlineCompletionMessages.push(project.title+(job.kind==='outline'?'的 PPT 大纲已生成':job.kind==='revise'?'的 PPT 页面已更新':'的 PPT 已生成，可以预览和下载'))
          }else{
            const outline=await getOutline(item.projectId)
            outlineCompletionMessages.push((outline.title??'项目')+(job.kind==='video_export'?'的MP4已导出完成':job.kind==='video'?('workflow' in job&&job.workflow==='html-preview-1'||outline.status==='preview_ready'?'的动画预览已就绪':'的视频已经生成完毕'):'的视频大纲已经生成完毕'))
          }
          removePendingOutlineNotification(item.jobId)
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
  if (['project-create', 'project-edit', 'project-outline', 'project-video', 'ppt-create', 'ppt-edit', 'ppt-outline', 'ppt-preview'].includes(String(route.name))) return 'make'
  if (route.name === 'project-drafts') return 'drafts'
  if (route.name === 'account-balance') return 'balance'
  if (route.name === 'account-settings') return 'account'
  return String(route.query.section ?? 'videos')
})
function teacherTarget(key:string) {
  if(key==='make')return {name:'project-create'}
  if(key==='videos')return {name:'project-list'}
  if(key==='drafts')return {name:'project-drafts'}
  if(key==='account')return {name:'account-settings'}
  return {name:'home',query:{section:key}}
}

async function onLogout() {
  clearCreationMemory()
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
  removeCreationNavigation()
  outlineNotificationDisposed = true
  clearTimeout(outlineNotificationTimer)
  outlineCompletionMessages = []
  outlineCompletionReminder?.close()
  window.removeEventListener(outlineNotificationEvent, handleOutlineNotificationPending)
})
</script>

<template>
  <div class="app-shell" :class="{ 'rail-collapsed': railCollapsed, 'creation-workspace': isCreationPage }">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <header class="app-header app-header--sticky">
      <div class="header-brand"><RouterLink :to="isAdmin ? { name: 'admin-page-config' } : { name: 'home', query: { section: 'videos' } }" class="brand"><AppIcon name="subject"/><span>教学视频助手</span></RouterLink></div>
      <nav class="app-nav" aria-label="账号">
        <RouterLink v-if="auth.user && !isAdmin" :to="{ name: 'account-settings' }" class="account-link" aria-label="打开账户设置"><UserAvatar :src="auth.avatarUrl" :name="auth.user.display_name || auth.user.username" /><span class="username">{{ auth.user.display_name || auth.user.username }}</span></RouterLink>
        <span v-else-if="auth.user" class="username">{{ auth.user.username }}</span>
        <RouterLink v-if="isAdmin" :to="{ name: 'admin' }" class="nav-link">管理后台</RouterLink>
        <el-button text @click="onLogout">退出</el-button>
      </nav>
    </header>

    <div class="app-body">
      <aside v-if="isAdmin" id="app-sidebar" class="side-rail side-rail--sticky" aria-label="管理员导航">
        <div class="rail-toolbar"><p class="rail-caption">管理员后台</p><button type="button" class="rail-toggle" :aria-label="railCollapsed ? '展开侧边栏' : '收起侧边栏'" :title="railCollapsed ? '展开侧边栏' : '收起侧边栏'" :aria-expanded="!railCollapsed" aria-controls="app-sidebar" @click="railCollapsed = !railCollapsed"><AppIcon :name="railCollapsed ? 'chevrons-right' : 'chevrons-left'"/></button></div>
        <RouterLink
          v-for="item in adminNav"
          :key="item.key"
          :title="item.label"
          :to="{ name: item.key }"
          class="rail-link"
          :class="{ active: route.name === item.key }"
          :aria-current="route.name === item.key ? 'page' : undefined"
        >
          <AppIcon :name="item.key"/><span>{{ item.label }}</span>
        </RouterLink>
      </aside>
      <aside v-else id="app-sidebar" class="side-rail side-rail--sticky" aria-label="教师导航">
        <div class="rail-toolbar"><button type="button" class="rail-toggle" :aria-label="railCollapsed ? '展开侧边栏' : '收起侧边栏'" :title="railCollapsed ? '展开侧边栏' : '收起侧边栏'" :aria-expanded="!railCollapsed" aria-controls="app-sidebar" @click="railCollapsed = !railCollapsed"><AppIcon :name="railCollapsed ? 'chevrons-right' : 'chevrons-left'"/></button></div>
        <RouterLink v-for="item in teacherNav" :key="item.key" :to="teacherTarget(item.key)" custom v-slot="{href,navigate}">
          <a :href="href" :title="item.label" class="rail-link"
             :class="{ active: activeTeacherKey === item.key }"
             :aria-current="activeTeacherKey === item.key ? 'page' : undefined"
             @click="item.key === 'make' ? startNewCreation($event) : navigate($event)">
            <AppIcon :name="item.icon"/><span>{{ item.label }}</span>
          </a>
        </RouterLink>
        <CreditBalanceLink/>
      </aside>

      <main id="main-content" class="app-main">
        <RouterView :key="`${route.path}:${creationSession}`" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell{min-height:100vh;background:var(--ev-color-bg)}
.header-brand{display:flex;align-items:center;gap:12px;min-width:0}.rail-toggle{display:grid;place-items:center;flex:none;width:36px;height:36px;border:1px solid transparent;border-radius:8px;background:transparent;color:var(--ev-color-muted);cursor:pointer}.rail-toolbar{display:flex;align-items:center;justify-content:flex-end;min-height:36px;margin:-16px 0 8px}.rail-toolbar .rail-caption{flex:1;margin:0 0 0 14px}.rail-toggle .app-icon{width:20px;height:20px}.rail-toggle:hover{background:var(--el-color-primary-light-9);color:var(--ev-color-primary)}
.skip-link{position:fixed;top:-80px;left:16px;z-index:2000;padding:12px 18px;border-radius:8px;background:var(--ev-color-primary);color:white}.skip-link:focus{top:10px}
.app-header{display:flex;align-items:center;justify-content:space-between;gap:16px;height:var(--ev-header-height);padding:0 30px 0 24px;border-bottom:1px solid var(--ev-color-border);background:var(--ev-color-surface)}
.brand{display:inline-flex;align-items:center;gap:10px;color:#2b4b7e;font-size:16px;font-weight:650;letter-spacing:.01em;text-decoration:none;white-space:nowrap}.brand .app-icon{width:30px;height:30px;color:var(--ev-color-primary)}
.account-link{display:inline-flex;align-items:center;gap:9px;min-width:0;text-decoration:none;--avatar-size:32px}.app-nav{display:flex;align-items:center;gap:18px;min-width:0;font-size:13px}.username{max-width:180px;overflow:hidden;color:var(--ev-color-muted);text-overflow:ellipsis;white-space:nowrap}.nav-link{color:var(--ev-color-primary-dark);font-size:13px;text-decoration:none}.nav-link:hover{text-decoration:underline}
.app-body{display:flex;min-height:calc(100vh - var(--ev-header-height))}
.side-rail{display:flex;flex-direction:column;gap:0;width:var(--ev-sidebar-width);flex:0 0 var(--ev-sidebar-width);padding:28px 14px;background:var(--ev-color-rail);border-right:1px solid #edf0f4}
.app-header--sticky{position:sticky;top:0;z-index:30}.side-rail--sticky{position:sticky;top:var(--ev-header-height);align-self:flex-start;height:calc(100vh - var(--ev-header-height));overflow-y:auto}
.rail-caption{margin:0 14px 18px;color:var(--ev-color-muted);font-size:11px;font-weight:400}.rail-link{display:flex;align-items:center;gap:12px;min-height:46px;margin:7px 0;padding:11px 14px;border:1px solid transparent;border-radius:8px;color:#647080;font-size:13px;text-decoration:none;white-space:nowrap}.rail-link .app-icon{width:19px;height:19px}.rail-link:hover{background:#f0f4fa;color:var(--ev-color-primary-dark)}.rail-link.active{background:#eaf2ff;color:var(--ev-color-primary-dark);font-weight:600}
.app-main{flex:1;min-width:0;width:100%;padding:34px clamp(24px,3.3vw,58px) 56px}.app-main>:deep(section){max-width:1420px;margin-left:auto;margin-right:auto}
@media(max-width:900px){.app-header{padding:0 22px}.app-body{display:block}.side-rail{width:100%;padding:9px 18px;display:flex;flex-direction:row;align-items:center;gap:5px;border-right:0;border-bottom:1px solid var(--ev-color-border);overflow-x:auto;scrollbar-width:thin}.side-rail--sticky{top:var(--ev-header-height);height:auto;z-index:25}.rail-caption{display:none}.rail-link{margin:0;justify-content:center;flex:1;padding:9px 12px;gap:8px;min-height:44px}.app-main{padding:28px 24px 42px}}
@media(max-width:650px){.app-header{padding:0 16px;gap:10px}.brand{font-size:14px;gap:7px}.brand .app-icon{width:24px;height:24px}.app-nav{gap:8px;font-size:12px}.username{max-width:84px}.nav-link{font-size:12px}.app-nav .el-button{padding:8px}.side-rail{padding:8px 9px;gap:2px}.rail-link{flex-direction:column;gap:4px;padding:7px 8px;font-size:11px;min-height:55px}.rail-link .app-icon{width:18px;height:18px}.app-main{padding:24px 16px 36px}}
@media(max-width:360px){.username{max-width:54px}.brand{font-size:13px}.app-header{padding:0 10px}.rail-link{padding:7px 5px}}
@media(min-width:901px){.side-rail{transition:width .24s ease,flex-basis .24s ease,padding .24s ease;overflow-x:hidden}.rail-link{position:relative}.rail-link>span{transition:opacity .16s ease}.rail-collapsed .side-rail{width:72px;flex-basis:72px;padding-left:10px;padding-right:10px}.rail-collapsed .rail-link{justify-content:center;padding:11px}.rail-collapsed .rail-link>span,.rail-collapsed .rail-caption{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;opacity:0}}
@media(max-width:900px){.rail-toolbar{display:none}.rail-toggle{display:none}.header-brand{gap:0}}
@media(min-width:901px){.rail-collapsed .rail-toolbar{justify-content:center}}
.creation-workspace .app-main{padding-top:16px;padding-bottom:16px}
@media(prefers-reduced-motion:reduce){.side-rail,.rail-link>span{transition:none}}
</style>
