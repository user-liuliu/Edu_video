import { expect, test } from 'vitest'
import type { CurrentUser } from '../src/api/auth'
import { decideRoute } from '../src/router/guards'

const T = (s: CurrentUser['status'], role: CurrentUser['role'] = 'teacher') => ({ id: '1', username: 'u', role, status: s })

test('anonymous to private → login', () => expect(decideRoute({ name: 'home', meta: {} }, null)).toEqual({ name: 'login' }))
test('anonymous to public ok', () => expect(decideRoute({ name: 'register', meta: { public: true } }, null)).toBe(true))
test('pending → account-status', () => expect(decideRoute({ name: 'home', meta: {} }, T('pending'))).toEqual({ name: 'account-status' }))
test('active on login → home', () => expect(decideRoute({ name: 'login', meta: { public: true } }, T('active'))).toEqual({ name: 'home' }))
test('teacher to admin → home', () => expect(decideRoute({ name: 'admin-users', meta: { admin: true } }, T('active'))).toEqual({ name: 'home' }))
test('admin to admin ok', () => expect(decideRoute({ name: 'admin-users', meta: { admin: true } }, T('active', 'admin'))).toBe(true))
test('active on account-status → home', () => expect(decideRoute({ name: 'account-status', meta: {} }, T('active'))).toEqual({ name: 'home' }))

test.each([
  { name: 'home', meta: {} },
  { name: 'login', meta: { public: true } },
  { name: 'register', meta: { public: true } },
  { name: 'account-status', meta: {} },
])('active admin on $name → page config', (target) => {
  expect(decideRoute(target, T('active', 'admin'))).toEqual({ name: 'admin-page-config' })
})

test.each([
  'project-create', 'project-list', 'project-edit', 'project-outline',
  'project-drafts', 'preferences', 'account-settings',
])('admin cannot enter teacher route %s', (name) => {
  expect(decideRoute({ name, meta: {} }, T('active', 'admin'))).toEqual({ name: 'admin-page-config' })
})

test.each([
  'project-create', 'project-list', 'project-edit', 'project-outline',
  'project-drafts', 'preferences', 'account-settings',
])('teacher can still enter teacher route %s', (name) => {
  expect(decideRoute({ name, meta: {} }, T('active'))).toBe(true)
})

test.each(['admin-page-config', 'admin-model-config', 'admin-users'])(
  'admin can enter management route %s', (name) => {
    expect(decideRoute({ name, meta: { admin: true } }, T('active', 'admin'))).toBe(true)
  },
)
