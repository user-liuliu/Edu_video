import { afterEach, expect, test, vi } from 'vitest'
import * as api from '../src/api/admin'

function mockFetch(status = 200, body: unknown = {}) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
    status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** 取第 n 次调用的方法、地址和请求体 */
function call(fetchMock: ReturnType<typeof mockFetch>, n = 0) {
  const [url, init] = fetchMock.mock.calls[n]
  return { url, method: init?.method, body: init?.body === undefined ? undefined : JSON.parse(String(init.body)) }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('listUsers builds the query and leaves out empty filters', async () => {
  const f = mockFetch(200, { items: [], total: 0 })
  await api.listUsers({ page: 1, page_size: 20 })
  expect(call(f).url).toBe('/api/admin/users?page=1&page_size=20')
  await api.listUsers({ status: 'pending', q: '  王 老师 ', page: 2, page_size: 50 })
  expect(call(f, 1).url).toBe('/api/admin/users?status=pending&q=%E7%8E%8B+%E8%80%81%E5%B8%88&page=2&page_size=50')
  await api.listUsers()
  expect(call(f, 2).url).toBe('/api/admin/users')
})

test('user actions use the backend routes and bodies', async () => {
  const f = mockFetch()
  await api.userAction('u1', 'approve')
  await api.setRole('u1', 'admin')
  await api.putRegistration(false)
  expect(call(f, 0)).toEqual({ url: '/api/admin/users/u1/actions', method: 'POST', body: { action: 'approve' } })
  expect(call(f, 1)).toEqual({ url: '/api/admin/users/u1/role', method: 'PUT', body: { role: 'admin' } })
  expect(call(f, 2)).toEqual({ url: '/api/admin/settings/registration', method: 'PUT', body: { open: false } })

  const f204 = mockFetch(204)
  await expect(api.resetPassword('u1', 'newpass123')).resolves.toBeUndefined()
  expect(call(f204)).toEqual({ url: '/api/admin/users/u1/password', method: 'POST', body: { password: 'newpass123' } })
})

test('settings and model config routes', async () => {
  const f = mockFetch()
  await api.getRegistration()
  await api.getFormFields()
  await api.putFormFields({ fields: [] })
  await api.getGenerationParams()
  await api.listModelConfigs()
  await api.putModelConfig('tts', { base_url: 'https://x', model: 'm', enabled: true })
  await api.testModelConfig('outline_llm')
  expect(fetchCalls(f)).toEqual([
    ['GET', '/api/admin/settings/registration'],
    ['GET', '/api/admin/settings/form-fields'],
    ['PUT', '/api/admin/settings/form-fields'],
    ['GET', '/api/admin/settings/generation-params'],
    ['GET', '/api/admin/model-configs'],
    ['PUT', '/api/admin/model-configs/tts'],
    ['POST', '/api/admin/model-configs/outline_llm/test'],
  ])
  // 没填 key 时请求体里不出现 api_key
  expect(call(f, 5).body).toEqual({ base_url: 'https://x', model: 'm', enabled: true })
})

function fetchCalls(f: ReturnType<typeof mockFetch>) {
  return f.mock.calls.map(([url, init]) => [init?.method, url])
}
