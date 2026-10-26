import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useAuthStore } from '../src/stores/auth'
import AccountSettingsView from '../src/views/workbench/AccountSettingsView.vue'

const wrappers: VueWrapper[] = []
let saved = { id: '1', username: 'teacher1', role: 'teacher' as const, status: 'active' as const, display_name: '林老师', gender: 'unspecified', school: '海滨中学', avatar_url: null as string | null }
let passwordError = false
let profileError = false
const requests: { url: string; init?: RequestInit }[] = []

beforeEach(() => {
  setActivePinia(createPinia())
  saved = { ...saved, display_name: '林老师', school: '海滨中学', avatar_url: null }
  useAuthStore().user = { ...saved, gender: 'unspecified' }
  passwordError = false
  profileError = false
  requests.length = 0
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    requests.push({ url, init })
    if (url === '/api/account/profile' && profileError && init?.method === 'GET') return new Response(JSON.stringify({ detail: { code: 'unavailable', message: '暂时无法加载资料' } }), { status: 503 })
    if (url === '/api/account/avatar' && init?.method === 'POST') saved.avatar_url = '/api/account/avatar'
    if (url === '/api/account/avatar' && init?.method === 'DELETE') { saved.avatar_url = null; return new Response(null, {status:204}) }
    if (url === '/api/account/password') {
      return passwordError
        ? new Response(JSON.stringify({ detail: { code: 'invalid_current_password', message: '原密码不正确' } }), { status: 401 })
        : new Response(null, { status: 204 })
    }
    if (url === '/api/preferences') {
      return new Response(JSON.stringify({ enabled: true, options: { teaching: ['多用生活实例'] }, items: [], suggestions: [] }))
    }
    if (init?.method === 'PATCH') saved = { ...saved, ...JSON.parse(String(init.body)) }
    return new Response(JSON.stringify(saved))
  }))
})

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

async function mountAccount(query = '') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/account', name: 'account-settings', component: AccountSettingsView }],
  })
  await router.push('/account' + query)
  await router.isReady()
  const wrapper = mount(AccountSettingsView, { global: { plugins: [router, ElementPlus] }, attachTo: document.body })
  wrappers.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}

function input(wrapper: VueWrapper, label: string) {
  const item = wrapper.findAll('.el-form-item').find((candidate) => candidate.find('label').text() === label)
  if (!item) throw new Error(`Missing form field: ${label}`)
  return item.get('input')
}

test('profile saves editable values and refreshes the shared user', async () => {
  const { wrapper } = await mountAccount()
  expect(wrapper.get('#tab-profile').attributes('aria-selected')).toBe('true')
  expect(input(wrapper, '登录用户名').attributes('readonly')).toBeDefined()
  await input(wrapper, '显示名称').setValue('王老师')
  await input(wrapper, '所属学校').setValue('  实验中学  ')
  await wrapper.get('#panel-profile form').trigger('submit')
  await flushPromises()

  const request = requests.find((item) => item.init?.method === 'PATCH')!
  expect(JSON.parse(String(request.init?.body))).toEqual({ display_name: '王老师', gender: 'unspecified', school: '实验中学' })
  expect(useAuthStore().user?.display_name).toBe('王老师')
  expect(wrapper.text()).toContain('资料已保存')
})

test('security tab changes URL and blocks mismatched passwords', async () => {
  const { wrapper, router } = await mountAccount()
  await wrapper.get('#tab-security').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query.tab).toBe('security')

  await input(wrapper, '原密码').setValue('pass1234')
  await input(wrapper, '新密码').setValue('newpass123')
  await input(wrapper, '确认新密码').setValue('different123')
  await wrapper.get('#panel-security form').trigger('submit')
  await flushPromises()

  await vi.waitFor(() => expect(wrapper.text()).toContain('两次输入的密码不一致'))
  expect(requests.some((item) => item.url === '/api/account/password')).toBe(false)
})

test('wrong current password shows inline failure and leaves user signed in', async () => {
  passwordError = true
  const { wrapper } = await mountAccount('?tab=security')
  await input(wrapper, '原密码').setValue('wrongpass')
  await input(wrapper, '新密码').setValue('newpass123')
  await input(wrapper, '确认新密码').setValue('newpass123')
  await wrapper.get('#panel-security form').trigger('submit')
  await flushPromises()

  await vi.waitFor(() => expect(wrapper.text()).toContain('原密码不正确'))
  expect(useAuthStore().user?.username).toBe('teacher1')
  expect(input(wrapper, '新密码').element.value).toBe('newpass123')
})

test('successful password change clears all password fields', async () => {
  const { wrapper } = await mountAccount('?tab=security')
  await input(wrapper, '原密码').setValue('pass1234')
  await input(wrapper, '新密码').setValue('newpass123')
  await input(wrapper, '确认新密码').setValue('newpass123')
  await wrapper.get('#panel-security form').trigger('submit')
  await flushPromises()

  expect(wrapper.text()).toContain('密码已修改')
  expect(input(wrapper, '原密码').element.value).toBe('')
  expect(input(wrapper, '新密码').element.value).toBe('')
})

test('preferences tab embeds current preference management', async () => {
  const { wrapper } = await mountAccount('?tab=preferences')
  expect(wrapper.findAll('h1')).toHaveLength(1)
  expect(wrapper.text()).toContain('确认保存偏好')
  expect(wrapper.text()).toContain('已保存偏好')
})

test('oversized avatar is rejected before making an upload request', async () => {
  const { wrapper } = await mountAccount()
  const file = new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'large.png', { type: 'image/png' })
  Object.defineProperty(wrapper.get('input[type=file]').element, 'files', { value: [file], configurable: true })
  await wrapper.get('input[type=file]').trigger('change')
  await flushPromises()

  expect(wrapper.text()).toContain('2 MiB')
  expect(requests.some((item) => item.url === '/api/account/avatar')).toBe(false)
})


test('failed profile load cannot overwrite stored personal details', async () => {
  profileError = true
  const { wrapper } = await mountAccount()
  expect(wrapper.text()).toContain('暂时无法加载资料')
  await wrapper.get('#panel-profile form').trigger('submit')
  await flushPromises()
  expect(requests.some(item => item.init?.method === 'PATCH')).toBe(false)
  expect(saved.school).toBe('海滨中学')
})

test('avatar upload updates shared avatar and preserves unsaved details', async () => {
  const NativeURL = URL
  vi.stubGlobal('URL', class extends NativeURL {
    static createObjectURL() { return 'blob:preview' }
    static revokeObjectURL() {}
  })
  const { wrapper } = await mountAccount()
  await input(wrapper, '所属学校').setValue('尚未保存的学校')
  const file = new File(['image'], 'avatar.png', {type:'image/png'})
  Object.defineProperty(wrapper.get('input[type=file]').element, 'files', {value:[file], configurable:true})
  await wrapper.get('input[type=file]').trigger('change')
  await wrapper.findAll('button').find(button => button.text() === '保存头像')!.trigger('click')
  await flushPromises()
  const upload = requests.find(item => item.url === '/api/account/avatar')!
  expect(upload.init?.body).toBeInstanceOf(FormData)
  expect((upload.init?.body as FormData).get('file')).toBe(file)
  expect(useAuthStore().avatarUrl).toBe('/api/account/avatar?v=1')
  expect(input(wrapper,'所属学校').element.value).toBe('尚未保存的学校')
  expect(wrapper.text()).toContain('头像已保存')
  await wrapper.findAll('button').find(button => button.text() === '恢复默认')!.trigger('click')
  await flushPromises()
  expect(useAuthStore().avatarUrl).toBeNull()
  expect(wrapper.text()).toContain('已恢复默认头像')
})
