import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useAuthStore } from '../src/stores/auth'

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubFetch(status: number, body?: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(body === undefined ? null : JSON.stringify(body), { status })),
  )
}

test('fetchMe: 401 → user null and loaded', async () => {
  stubFetch(401, { detail: { code: 'not_authenticated', message: '请先登录' } })
  const auth = useAuthStore()
  await auth.fetchMe()
  expect(auth.user).toBeNull()
  expect(auth.loaded).toBe(true)
})

test('fetchMe: success stores user', async () => {
  const me = { id: '1', username: 'u', role: 'teacher', status: 'active', created_at: '2026-10-16T00:00:00Z' }
  stubFetch(200, me)
  const auth = useAuthStore()
  await auth.fetchMe()
  expect(auth.user).toEqual(me)
  expect(auth.loaded).toBe(true)
})

test('fetchMe: other errors propagate and stay not loaded', async () => {
  stubFetch(500, { detail: { code: 'internal_error', message: '服务器出错' } })
  const auth = useAuthStore()
  await expect(auth.fetchMe()).rejects.toMatchObject({ code: 'internal_error' })
  expect(auth.loaded).toBe(false)
})

test('logout clears user', async () => {
  localStorage.setItem('edu-video:draft:project:new', JSON.stringify({prompt:'临时内容'}))
  localStorage.setItem('edu-video:draft:project:p1', JSON.stringify({prompt:'未保存修改'}))
  stubFetch(200, { id: '1', username: 'u', role: 'admin', status: 'active' })
  const auth = useAuthStore()
  await auth.login('u', 'p')
  expect(auth.user?.role).toBe('admin')
  stubFetch(204)
  await auth.logout()
  expect(auth.user).toBeNull()
  expect(localStorage.getItem('edu-video:draft:project:new')).toBeNull()
  expect(localStorage.getItem('edu-video:draft:project:p1')).toBeNull()
})
