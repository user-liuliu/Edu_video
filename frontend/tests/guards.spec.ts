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
