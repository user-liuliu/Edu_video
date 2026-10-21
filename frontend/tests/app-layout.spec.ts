import { mount } from '@vue/test-utils'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { flushPromises } from '@vue/test-utils'
import type { CurrentUser } from '../src/api/auth'
import AppLayout from '../src/layouts/AppLayout.vue'
import OutlineView from '../src/views/workbench/OutlineView.vue'
import { useAuthStore } from '../src/stores/auth'

const Empty = { template: '<div />' }
const mounted: { unmount: () => void }[] = []

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Empty },
      { path: '/projects/new', name: 'project-create', component: Empty },
      { path: '/projects', name: 'project-list', component: Empty },
      { path: '/projects/:id/outline', name: 'project-outline', component: OutlineView },
      { path: '/drafts', name: 'project-drafts', component: Empty },
      { path: '/preferences', name: 'preferences', component: Empty },
      {
        path: '/admin',
        name: 'admin',
        component: Empty,
        children: [
          { path: 'page-config', name: 'admin-page-config', component: Empty },
          { path: 'model-config', name: 'admin-model-config', component: Empty },
          { path: 'users', name: 'admin-users', component: Empty },
        ],
      },
      { path: '/login', name: 'login', component: Empty },
    ],
  })
}

async function mountAs(role: CurrentUser['role'], path = '/') {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = { id: '1', username: '王老师', role, status: 'active' }
  const router = makeRouter()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(AppLayout, { global: { plugins: [pinia, router, ElementPlus] } })
  mounted.push(wrapper)
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
})

afterEach(async () => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  ElMessageBox.close()
  ElMessage.closeAll()
  await flushPromises()
  sessionStorage.clear()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

test('header shows brand, username, logout and landmarks', async () => {
  const w = await mountAs('teacher')
  expect(w.find('header').text()).toContain('教学视频助手')
  expect(w.find('nav').text()).toContain('王老师')
  expect(w.find('nav').text()).toContain('退出')
  expect(w.find('[aria-label="教师导航"]').text()).toContain('视频制作')
  expect(w.find('[aria-label="教师导航"]').text()).toContain('草稿箱')
  expect(w.find('[aria-label="教师导航"]').text()).toContain('我的偏好')
  expect(w.find('main').exists()).toBe(true)
})

test('side rail uses the sticky navigation variant', async () => {
  const w = await mountAs('teacher')
  expect(w.find('.side-rail').classes()).toContain('side-rail--sticky')
})

test('sidebar can collapse and expand while all navigation links remain accessible', async () => {
  const w=await mountAs('teacher','/projects/new')
  expect(w.find('aside').text()).not.toContain('教师工作台')
  const toggle=w.get('button[aria-label="收起侧边栏"]')
  expect(w.find('header .rail-toggle').exists()).toBe(false)
  expect(w.find('aside .rail-toolbar .rail-toggle').exists()).toBe(true)
  expect(toggle.attributes('aria-expanded')).toBe('true')
  await toggle.trigger('click')
  expect(w.get('.app-shell').classes()).toContain('rail-collapsed')
  expect(w.get('button[aria-label="展开侧边栏"]').attributes('aria-expanded')).toBe('false')
  expect(w.findAll('.rail-link')).toHaveLength(5)
  expect(w.findAll('.rail-link').every(link=>!!link.attributes('title'))).toBe(true)
  await w.get('button[aria-label="展开侧边栏"]').trigger('click')
  expect(w.get('.app-shell').classes()).not.toContain('rail-collapsed')
})

test('light rail has decorative icons with readable links and no duplicate new entry', async () => {
  const w=await mountAs('teacher', '/projects/new')
  const links=w.findAll('.rail-link')
  expect(links).toHaveLength(5)
  expect(links.every(link=>link.find('svg[aria-hidden="true"]').exists())).toBe(true)
  expect(links.find(link=>link.text()==='视频制作')?.attributes('aria-current')).toBe('page')
  expect(w.find('.skip-link[href="#main-content"]').exists()).toBe(true)
  expect(w.find('aside').text()).not.toContain('新建视频')
})

test('header uses the sticky navigation variant', async () => {
  const w = await mountAs('teacher')
  expect(w.find('header').classes()).toContain('app-header--sticky')
})

test('teacher does not see admin entry', async () => {
  const w = await mountAs('teacher')
  expect(w.text()).not.toContain('管理后台')
})

test('admin sees admin entry', async () => {
  const w = await mountAs('admin')
  expect(w.find('aside .rail-toolbar .rail-toggle').exists()).toBe(true)
  expect(w.text()).toContain('管理后台')
  expect(w.find('[aria-label="管理员导航"]').text()).toContain('页面配置')
  expect(w.find('[aria-label="管理员导航"]').text()).toContain('模型配置')
  expect(w.find('[aria-label="管理员导航"]').text()).toContain('用户管理')
})

test('admin header does not offer the teacher workbench', async () => {
  const w = await mountAs('admin')
  expect(w.find('header').text()).not.toContain('教师工作台')
  expect(w.find('header a[href="/projects"]').exists()).toBe(false)
})

test('admin always sees management navigation even on a stale teacher URL', async () => {
  const w = await mountAs('admin', '/projects/new')
  expect(w.find('[aria-label="教师导航"]').exists()).toBe(false)
  expect(w.find('[aria-label="管理员导航"]').findAll('a').map((a) => a.text()))
    .toEqual(['页面配置', '模型配置', '用户管理'])
})

function completionDialogs() {
  return Array.from(document.querySelectorAll<HTMLElement>('.el-overlay')).filter(overlay => overlay.style.display !== 'none')
    .map(overlay => overlay.querySelector<HTMLElement>('[role="dialog"][aria-label="大纲生成完成"]')).filter((dialog): dialog is HTMLElement => dialog !== null)
}

function notificationJobs(ids = ['j1']) {
  sessionStorage.setItem('edu-video:outline-job-notification', JSON.stringify(ids.map((jobId, index) => ({jobId, projectId: 'p' + (index + 1)}))))
}

function jobResponse(id: string, status: string) {
  return {id,project_id:'p'+id.slice(1),kind:'generate',status,stage:status==='succeeded'?'处理完成':'生成大纲',progress:status==='succeeded'?100:45,error_message:null}
}

function outlineResponse(id: string, title: string) {
  return {project_id:id,title,revision:2,status:'outline_ready',segments:[],job_id:'j'+id.slice(1),needs_regeneration:false,material_warnings:[]}
}

function completionReminders() {
  return Array.from(document.querySelectorAll<HTMLElement>('.el-message--success')).filter(message => message.style.display !== 'none')
}

test('completion shows a three-second reminder after navigating away without repeating on reentry', async () => {
  vi.useFakeTimers()
  notificationJobs()
  let completed = false
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(
    url.includes('/api/jobs/') ? jobResponse('j1', completed ? 'succeeded' : 'running') : outlineResponse('p1','二次函数'),
  ))))
  const wrapper = await mountAs('teacher', '/projects/new')
  await flushPromises()
  expect(completionReminders()).toHaveLength(0)
  await wrapper.vm.$router.push('/projects')
  completed = true
  await vi.advanceTimersByTimeAsync(1000)
  await flushPromises()
  expect(completionDialogs()).toHaveLength(0)
  expect(completionReminders()).toHaveLength(1)
  expect(completionReminders()[0]!.textContent).toContain('二次函数的视频大纲已经生成完毕')
  expect(completionReminders()[0]!.querySelector('button')).toBeNull()
  await vi.advanceTimersByTimeAsync(2999)
  expect(completionReminders()).toHaveLength(1)
  await vi.advanceTimersByTimeAsync(1)
  await flushPromises()
  expect(completionReminders()).toHaveLength(0)
  expect(sessionStorage.getItem('edu-video:outline-job-notification')).toBeNull()
  await wrapper.vm.$router.push('/projects/p1/outline')
  await flushPromises()
  expect(wrapper.find('h1').text()).toBe('大纲草稿')
  await wrapper.vm.$router.push('/projects')
  await wrapper.vm.$router.push('/projects/p1/outline')
  await flushPromises()
  await vi.advanceTimersByTimeAsync(2000)
  expect(completionReminders()).toHaveLength(0)
})

test('several completed jobs show reminders by completion time rather than submission order', async () => {
  vi.useFakeTimers()
  notificationJobs(['j1','j2','j3'])
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.includes('/api/jobs/')) {
      const id = url.split('/').pop()!
      const times: Record<string,string> = {j1:'2026-10-18T00:00:03Z',j2:'2026-10-18T00:00:01Z',j3:'2026-10-18T00:00:02Z'}
      return new Response(JSON.stringify({...jobResponse(id,'succeeded'),updated_at:times[id]}))
    }
    const id = url.split('/')[3]!
    return new Response(JSON.stringify(outlineResponse(id,{p1:'函数',p2:'几何',p3:'电路'}[id]!)))
  }))
  await mountAs('teacher', '/projects')
  await flushPromises()
  for (const title of ['几何','电路','函数']) {
    expect(completionDialogs()).toHaveLength(0)
    expect(completionReminders()).toHaveLength(1)
    expect(completionReminders()[0]!.textContent).toContain(title+'的视频大纲已经生成完毕')
    await vi.advanceTimersByTimeAsync(2999)
    expect(completionReminders()).toHaveLength(1)
    expect(completionReminders()[0]!.textContent).toContain(title+'的视频大纲已经生成完毕')
    await vi.advanceTimersByTimeAsync(1)
    await flushPromises()
  }
  expect(completionReminders()).toHaveLength(0)
  expect(sessionStorage.getItem('edu-video:outline-job-notification')).toBeNull()
})

test('a later submitted job can finish first while earlier jobs continue and join the reminder queue later', async () => {
  vi.useFakeTimers()
  notificationJobs(['j1','j2'])
  let firstFinished=false
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.includes('/api/jobs/')) {
      const id=url.split('/').pop()!
      return new Response(JSON.stringify({...jobResponse(id,id==='j2'||firstFinished?'succeeded':'running'),updated_at:id==='j2'?'2026-10-18T00:00:01Z':'2026-10-18T00:00:02Z'}))
    }
    const id=url.split('/')[3]!
    return new Response(JSON.stringify(outlineResponse(id,id==='p1'?'函数':'几何')))
  }))
  await mountAs('teacher','/projects')
  await flushPromises()
  expect(completionReminders()[0]!.textContent).toContain('几何的视频大纲已经生成完毕')
  firstFinished=true
  await vi.advanceTimersByTimeAsync(1000)
  await flushPromises()
  expect(completionReminders()).toHaveLength(1)
  expect(completionReminders()[0]!.textContent).toContain('几何的视频大纲已经生成完毕')
  await vi.advanceTimersByTimeAsync(2000)
  await flushPromises()
  expect(completionReminders()).toHaveLength(1)
  expect(completionReminders()[0]!.textContent).toContain('函数的视频大纲已经生成完毕')
  await vi.advanceTimersByTimeAsync(3000)
  await flushPromises()
  expect(completionReminders()).toHaveLength(0)
})

test('failed jobs do not show a completion reminder', async () => {
  vi.useFakeTimers()
  notificationJobs()
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(jobResponse('j1','failed')))))
  await mountAs('teacher', '/projects')
  await flushPromises()
  await vi.advanceTimersByTimeAsync(4000)
  expect(completionDialogs()).toHaveLength(0)
  expect(completionReminders()).toHaveLength(0)
  expect(sessionStorage.getItem('edu-video:outline-job-notification')).toBeNull()
})

test('outline and video completions share a sequential three second reminder queue',async()=>{
  vi.useFakeTimers()
  notificationJobs(['j1','j2'])
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
    if(url.includes('/api/jobs/')){
      const id=url.split('/').pop()!
      return new Response(JSON.stringify({...jobResponse(id,'succeeded'),kind:id==='j1'?'generate':'video',updated_at:id==='j2'?'2026-10-18T00:00:01Z':'2026-10-18T00:00:02Z'}))
    }
    return new Response(JSON.stringify(outlineResponse('p1','函数')))
  }))
  await mountAs('teacher','/projects');await flushPromises()
  expect(completionReminders()[0]!.textContent).toContain('函数的视频已经生成完毕')
  await vi.advanceTimersByTimeAsync(3000);await flushPromises()
  expect(completionReminders()[0]!.textContent).toContain('函数的视频大纲已经生成完毕')
  await vi.advanceTimersByTimeAsync(3000);await flushPromises()
  expect(completionReminders()).toHaveLength(0)
})


test('preview and export completions join the same ordered reminder queue',async()=>{
 vi.useFakeTimers();notificationJobs(['j1','j2'])
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url.includes('/api/jobs/')){const id=url.split('/').pop()!;return new Response(JSON.stringify({...jobResponse(id,'succeeded'),kind:id==='j1'?'video':'video_export',payload:{workflow:'html-preview-1'},updated_at:id==='j1'?'2026-10-18T00:00:01Z':'2026-10-18T00:00:02Z'}))}
  return new Response(JSON.stringify({...outlineResponse('p1','函数'),status:'preview_ready'}))
 }))
 await mountAs('teacher','/projects');await flushPromises()
 expect(completionReminders()[0]?.textContent).toContain('函数的动画预览已就绪')
 await vi.advanceTimersByTimeAsync(3000);await flushPromises()
 expect(completionReminders()[0]?.textContent).toContain('函数的MP4已导出完成')
})
