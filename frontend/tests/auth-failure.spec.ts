import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import type { CurrentUser } from '../src/api/auth'
import { ApiError } from '../src/api/http'
import { createAuthFailureHandler } from '../src/router/authFailure'
import { useAuthStore } from '../src/stores/auth'

const Empty = { template: '<div />' }

const me = (status: CurrentUser['status'], role: CurrentUser['role'] = 'admin'): CurrentUser => ({
  id: '1',
  username: '王老师',
  role,
  status,
})

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Empty },
      { path: '/login', name: 'login', component: Empty, meta: { public: true } },
      { path: '/account-status', name: 'account-status', component: Empty },
      { path: '/admin/users', name: 'admin-users', component: Empty, meta: { admin: true } },
    ],
  })
}

let router: Router
let auth: ReturnType<typeof useAuthStore>

beforeEach(async () => {
  setActivePinia(createPinia())
  auth = useAuthStore()
  auth.user = me('active')
  auth.loaded = true
  router = makeRouter()
  await router.push('/admin/users')
  await router.isReady()
})

test('401 not_authenticated → clears the user and goes to login', async () => {
  const fetchMe = vi.spyOn(auth, 'fetchMe')
  const handle = createAuthFailureHandler(router)
  await handle(new ApiError(401, 'not_authenticated', '请先登录'), '/api/admin/users')
  expect(auth.user).toBeNull()
  expect(auth.loaded).toBe(true)
  expect(router.currentRoute.value.name).toBe('login')
  expect(fetchMe).not.toHaveBeenCalled()
})

test('401 on a public page → stays there', async () => {
  await router.push('/login')
  const handle = createAuthFailureHandler(router)
  const replace = vi.spyOn(router, 'replace')
  await handle(new ApiError(401, 'not_authenticated', '请先登录'), '/api/public/x')
  expect(auth.user).toBeNull()
  expect(replace).not.toHaveBeenCalled()
})

test('403 account_disabled → re-reads the user and goes to account-status', async () => {
  const fetchMe = vi.spyOn(auth, 'fetchMe').mockImplementation(async () => {
    auth.user = me('disabled')
  })
  const handle = createAuthFailureHandler(router)
  await handle(new ApiError(403, 'account_disabled', '账号已停用'), '/api/admin/users')
  expect(fetchMe).toHaveBeenCalledTimes(1)
  expect(router.currentRoute.value.name).toBe('account-status')
})

test('403 forbidden after losing admin → home', async () => {
  vi.spyOn(auth, 'fetchMe').mockImplementation(async () => {
    auth.user = me('active', 'teacher')
  })
  const handle = createAuthFailureHandler(router)
  await handle(new ApiError(403, 'forbidden', '没有权限'), '/api/admin/users')
  expect(router.currentRoute.value.name).toBe('home')
})

test('403 but the user is still allowed here → stays', async () => {
  vi.spyOn(auth, 'fetchMe').mockResolvedValue(undefined)
  const handle = createAuthFailureHandler(router)
  const replace = vi.spyOn(router, 'replace')
  await handle(new ApiError(403, 'forbidden', '没有权限'), '/api/admin/users')
  expect(replace).not.toHaveBeenCalled()
  expect(router.currentRoute.value.name).toBe('admin-users')
})

test('concurrent failures are handled once', async () => {
  let release!: () => void
  const fetchMe = vi.spyOn(auth, 'fetchMe').mockImplementation(
    () =>
      new Promise<void>((resolve) => {
        release = () => {
          auth.user = me('disabled')
          resolve()
        }
      }),
  )
  const handle = createAuthFailureHandler(router)
  const err = new ApiError(403, 'account_disabled', '账号已停用')
  const first = handle(err, '/api/admin/users')
  const second = handle(err, '/api/admin/settings/registration')
  release()
  await Promise.all([first, second])
  expect(fetchMe).toHaveBeenCalledTimes(1)
  expect(router.currentRoute.value.name).toBe('account-status')
})
