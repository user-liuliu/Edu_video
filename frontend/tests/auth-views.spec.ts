import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import type { Component } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import type { CurrentUser } from '../src/api/auth'
import { ApiError } from '../src/api/http'
import { useAuthStore } from '../src/stores/auth'
import AccountStatusView from '../src/views/AccountStatusView.vue'
import LoginView from '../src/views/LoginView.vue'
import RegisterView from '../src/views/RegisterView.vue'

const Empty = { template: '<div />' }

const user = (status: CurrentUser['status']): CurrentUser => ({ id: '1', username: '王老师', role: 'teacher', status })

let pinia: ReturnType<typeof createPinia>

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
})

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Empty },
      { path: '/login', name: 'login', component: Empty },
      { path: '/register', name: 'register', component: Empty },
      { path: '/account-status', name: 'account-status', component: Empty },
    ],
  })
}

async function mountView(view: Component, path: string): Promise<{ w: VueWrapper; router: Router }> {
  const router = makeRouter()
  await router.push(path)
  await router.isReady()
  const w = mount(view, { global: { plugins: [pinia, router, ElementPlus] }, attachTo: document.body })
  return { w, router }
}

/** 按可见的标签文字找到表单项里的输入框 */
function field(w: VueWrapper, label: string) {
  const item = w.findAll('.el-form-item').find((i) => i.find('label').text() === label)
  if (!item) throw new Error(`没有找到标签为「${label}」的输入框`)
  const input = item.find('input')
  // 标签和输入框必须关联起来，读屏软件才能读出字段名
  expect(item.find('label').attributes('for')).toBe(input.attributes('id'))
  return input
}

async function submit(w: VueWrapper) {
  await w.find('form').trigger('submit')
  await flushPromises()
}

test('register: mismatched confirm blocks submit', async () => {
  const register = vi.spyOn(useAuthStore(), 'register')
  const { w } = await mountView(RegisterView, '/register')
  await field(w, '用户名').setValue('王老师')
  await field(w, '密码').setValue('pass1234')
  await field(w, '确认密码').setValue('pass12345')
  await submit(w)
  await vi.waitFor(() => expect(w.text()).toContain('两次输入的密码不一致'))
  expect(register).not.toHaveBeenCalled()
  w.unmount()
})

test('register: invalid username and short password block submit', async () => {
  const register = vi.spyOn(useAuthStore(), 'register')
  const { w } = await mountView(RegisterView, '/register')
  await field(w, '用户名').setValue('ab')
  await field(w, '密码').setValue('short')
  await field(w, '确认密码').setValue('short')
  await submit(w)
  await vi.waitFor(() => {
    expect(w.text()).toContain('用户名为 3–32 位，只能包含字母、数字、下划线和汉字')
    expect(w.text()).toContain('密码长度为 8–128 位')
  })
  expect(register).not.toHaveBeenCalled()
  w.unmount()
})

test('register: success shows pending notice', async () => {
  const register = vi.spyOn(useAuthStore(), 'register').mockResolvedValue(user('pending'))
  const { w, router } = await mountView(RegisterView, '/register')
  await field(w, '用户名').setValue('  王老师  ')
  await field(w, '密码').setValue('pass1234')
  await field(w, '确认密码').setValue('pass1234')
  await submit(w)
  expect(register).toHaveBeenCalledWith('王老师', 'pass1234')
  expect(w.text()).toContain('注册成功，请等待管理员审核')
  expect(w.find('form').exists()).toBe(false)
  // 不自动登录：仍停在注册页，提供去登录的入口
  expect(router.currentRoute.value.name).toBe('register')
  const toLogin = w.findAll('a').find((a) => a.text() === '去登录')
  expect(toLogin?.attributes('href')).toBe('/login')
  w.unmount()
})

test('register: shows server message for registration_closed', async () => {
  vi.spyOn(useAuthStore(), 'register').mockRejectedValue(new ApiError(403, 'registration_closed', '暂未开放注册'))
  const { w } = await mountView(RegisterView, '/register')
  await field(w, '用户名').setValue('王老师')
  await field(w, '密码').setValue('pass1234')
  await field(w, '确认密码').setValue('pass1234')
  await submit(w)
  expect(w.find('[role="alert"]').text()).toBe('暂未开放注册')
  expect(w.text()).not.toContain('注册成功')
  w.unmount()
})

test('login: 429 shows lock message', async () => {
  const login = vi
    .spyOn(useAuthStore(), 'login')
    .mockRejectedValue(new ApiError(429, 'login_locked', '登录失败次数过多，请稍后再试（最长 15 分钟）'))
  const { w, router } = await mountView(LoginView, '/login')
  await field(w, '用户名').setValue('王老师')
  await field(w, '密码').setValue('pass1234')
  await submit(w)
  expect(login).toHaveBeenCalledWith('王老师', 'pass1234')
  expect(w.find('[role="alert"]').text()).toBe('登录失败次数过多，请稍后再试（最长 15 分钟）')
  expect(router.currentRoute.value.name).toBe('login')
  w.unmount()
})

test('login: pending user routes to account-status', async () => {
  const auth = useAuthStore()
  const login = vi.spyOn(auth, 'login').mockImplementation(async () => {
    auth.user = user('pending')
    return auth.user
  })
  const { w, router } = await mountView(LoginView, '/login')
  await field(w, '用户名').setValue('王老师')
  await field(w, '密码').setValue('pass1234')
  await submit(w)
  expect(login).toHaveBeenCalledWith('王老师', 'pass1234')
  expect(router.currentRoute.value.name).toBe('account-status')
  w.unmount()
})

test('login: active user routes to home', async () => {
  const auth = useAuthStore()
  vi.spyOn(auth, 'login').mockImplementation(async () => {
    auth.user = user('active')
    return auth.user
  })
  const { w, router } = await mountView(LoginView, '/login')
  await field(w, '用户名').setValue('王老师')
  await field(w, '密码').setValue('pass1234')
  await submit(w)
  expect(router.currentRoute.value.name).toBe('home')
  w.unmount()
})

test('login: submit button is disabled and loading while submitting', async () => {
  let finish!: () => void
  vi.spyOn(useAuthStore(), 'login').mockImplementation(
    () => new Promise((_resolve, reject) => (finish = () => reject(new ApiError(401, 'invalid_credentials', '用户名或密码错误')))),
  )
  const { w } = await mountView(LoginView, '/login')
  await field(w, '用户名').setValue('王老师')
  await field(w, '密码').setValue('pass1234')
  await submit(w)
  const button = () => w.find('button[type="submit"]')
  expect(button().attributes('disabled')).toBeDefined()
  expect(button().classes()).toContain('is-loading')
  finish()
  await flushPromises()
  expect(button().attributes('disabled')).toBeUndefined()
  expect(w.find('[role="alert"]').text()).toBe('用户名或密码错误')
  w.unmount()
})

test('register: hints are linked to their inputs', async () => {
  const { w } = await mountView(RegisterView, '/register')
  expect(w.find(`#${field(w, '用户名').attributes('aria-describedby')}`).text()).toContain('3–32 位')
  expect(w.find(`#${field(w, '密码').attributes('aria-describedby')}`).text()).toContain('8–128 位')
  w.unmount()
})

test('login: empty fields block submit', async () => {
  const login = vi.spyOn(useAuthStore(), 'login')
  const { w } = await mountView(LoginView, '/login')
  await submit(w)
  await vi.waitFor(() => {
    expect(w.text()).toContain('请输入用户名')
    expect(w.text()).toContain('请输入密码')
  })
  expect(login).not.toHaveBeenCalled()
  w.unmount()
})

test.each([
  ['pending', '账号正在等待管理员审核'],
  ['rejected', '注册申请未通过'],
  ['disabled', '账号已被停用'],
] as const)('status page %s', async (status, message) => {
  useAuthStore().user = user(status)
  const { w } = await mountView(AccountStatusView, '/account-status')
  expect(w.findAll('h1')).toHaveLength(1)
  expect(w.text()).toContain(message)
  expect(w.text()).toContain('如有疑问请联系管理员')
  w.unmount()
})

test('status page: 退出登录 logs out and routes to login', async () => {
  const auth = useAuthStore()
  auth.user = user('pending')
  const logout = vi.spyOn(auth, 'logout').mockImplementation(async () => {
    auth.user = null
  })
  const { w, router } = await mountView(AccountStatusView, '/account-status')
  const button = w.findAll('button').find((b) => b.text() === '退出登录')
  await button!.trigger('click')
  await flushPromises()
  expect(logout).toHaveBeenCalled()
  expect(router.currentRoute.value.name).toBe('login')
  w.unmount()
})
