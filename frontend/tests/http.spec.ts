import { afterEach, expect, test, vi } from 'vitest'
import { ApiError, errorText, request, setAuthFailureHandler } from '../src/api/http'

function mockFetch(status: number, body?: unknown) {
  const fetchMock = vi.fn(async () =>
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
  setAuthFailureHandler(null)
})

test('business error → ApiError with detail.code and detail.message', async () => {
  mockFetch(409, { detail: { code: 'username_taken', message: '用户名已被使用' } })
  const err = await request('POST', '/api/auth/register', { username: 'u', password: 'p' }).catch((e: unknown) => e)
  expect(err).toBeInstanceOf(ApiError)
  expect(err).toMatchObject({ status: 409, code: 'username_taken', message: '用户名已被使用' })
})

test('422 → validation_error with the first message', async () => {
  mockFetch(422, { detail: [{ type: 'string_too_short', loc: ['body', 'password'], msg: '密码太短' }] })
  const err = await request('POST', '/api/auth/register', {}).catch((e: unknown) => e)
  expect(err).toBeInstanceOf(ApiError)
  expect(err).toMatchObject({ status: 422, code: 'validation_error', message: '密码太短' })
})

test('204 → undefined', async () => {
  mockFetch(204)
  await expect(request('POST', '/api/auth/logout')).resolves.toBeUndefined()
})

test('sends JSON body with same-origin credentials', async () => {
  const fetchMock = mockFetch(200, { ok: true })
  await expect(request('POST', '/api/auth/login', { username: 'u', password: 'p' })).resolves.toEqual({ ok: true })
  expect(fetchMock).toHaveBeenCalledWith('/api/auth/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'u', password: 'p' }),
  })
})

test('errorText: validation_error keeps Chinese messages (without the pydantic prefix), hides English ones', () => {
  expect(errorText(new ApiError(422, 'validation_error', 'Value error, 用户名只能包含字母、数字、下划线和汉字'))).toBe(
    '用户名只能包含字母、数字、下划线和汉字',
  )
  expect(errorText(new ApiError(422, 'validation_error', 'String should have at least 8 characters'))).toBe(
    '提交的内容不符合要求，请检查后重试',
  )
})

test('errorText: other ApiError → its message', () => {
  expect(errorText(new ApiError(429, 'login_locked', '登录失败次数过多，请稍后再试（最长 15 分钟）'))).toBe(
    '登录失败次数过多，请稍后再试（最长 15 分钟）',
  )
})

test('errorText: anything else → generic message', () => {
  expect(errorText(new TypeError('boom'))).toBe('操作失败，请稍后重试')
  expect(errorText(undefined)).toBe('操作失败，请稍后重试')
})

test('auth failure handler: called on 401 not_authenticated, then still throws', async () => {
  const handler = vi.fn()
  setAuthFailureHandler(handler)
  mockFetch(401, { detail: { code: 'not_authenticated', message: '请先登录' } })
  const err = await request('GET', '/api/admin/users').catch((e: unknown) => e)
  expect(err).toMatchObject({ status: 401, code: 'not_authenticated' })
  expect(handler).toHaveBeenCalledTimes(1)
  expect(handler).toHaveBeenCalledWith(err, '/api/admin/users')
})

test('auth failure handler: called on 403 account / forbidden codes', async () => {
  const handler = vi.fn()
  setAuthFailureHandler(handler)
  for (const code of ['account_pending', 'account_rejected', 'account_disabled', 'forbidden']) {
    mockFetch(403, { detail: { code, message: 'x' } })
    await expect(request('GET', '/api/admin/users')).rejects.toMatchObject({ status: 403, code })
  }
  expect(handler.mock.calls.map(([e]) => (e as ApiError).code)).toEqual([
    'account_pending',
    'account_rejected',
    'account_disabled',
    'forbidden',
  ])
})

test('auth failure handler: not called for auth endpoints or other errors', async () => {
  const handler = vi.fn()
  setAuthFailureHandler(handler)
  mockFetch(401, { detail: { code: 'invalid_credentials', message: '用户名或密码错误' } })
  await expect(request('POST', '/api/auth/login', {})).rejects.toBeInstanceOf(ApiError)
  for (const path of ['/api/auth/login', '/api/auth/register', '/api/auth/me']) {
    mockFetch(401, { detail: { code: 'not_authenticated', message: '请先登录' } })
    await expect(request('POST', path, {})).rejects.toBeInstanceOf(ApiError)
  }
  mockFetch(403, { detail: { code: 'registration_closed', message: '暂未开放注册' } })
  await expect(request('GET', '/api/admin/users')).rejects.toBeInstanceOf(ApiError)
  mockFetch(409, { detail: { code: 'last_admin', message: 'x' } })
  await expect(request('GET', '/api/admin/users')).rejects.toBeInstanceOf(ApiError)
  expect(handler).not.toHaveBeenCalled()
})
