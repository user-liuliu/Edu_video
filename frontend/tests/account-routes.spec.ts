import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test } from 'vitest'
import { useAuthStore } from '../src/stores/auth'
import { router } from '../src/router'

beforeEach(() => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore(pinia)
  auth.loaded = true
  auth.user = { id: '1', username: 'teacher1', role: 'teacher', status: 'active' }
})

test('legacy preference and account URLs resolve to their account settings tabs', async () => {
  await router.push('/preferences')
  expect(router.currentRoute.value.name).toBe('account-settings')
  expect(router.currentRoute.value.query.tab).toBe('preferences')

  await router.push('/?section=account')
  expect(router.currentRoute.value.name).toBe('account-settings')
  expect(router.currentRoute.value.query.tab).toBe('profile')
})
