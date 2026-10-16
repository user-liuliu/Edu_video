import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { CurrentUser } from '../src/api/auth'
import AppLayout from '../src/layouts/AppLayout.vue'
import { useAuthStore } from '../src/stores/auth'

const Empty = { template: '<div />' }

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Empty },
      { path: '/admin', name: 'admin', component: Empty },
      { path: '/login', name: 'login', component: Empty },
    ],
  })
}

async function mountAs(role: CurrentUser['role']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = { id: '1', username: '王老师', role, status: 'active' }
  const router = makeRouter()
  await router.push('/')
  await router.isReady()
  return mount(AppLayout, { global: { plugins: [pinia, router, ElementPlus] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
})

test('header shows brand, username, logout and landmarks', async () => {
  const w = await mountAs('teacher')
  expect(w.find('header').text()).toContain('教学视频助手')
  expect(w.find('nav').text()).toContain('王老师')
  expect(w.find('nav').text()).toContain('退出')
  expect(w.find('main').exists()).toBe(true)
})

test('teacher does not see admin entry', async () => {
  const w = await mountAs('teacher')
  expect(w.text()).not.toContain('管理后台')
})

test('admin sees admin entry', async () => {
  const w = await mountAs('admin')
  expect(w.text()).toContain('管理后台')
})
