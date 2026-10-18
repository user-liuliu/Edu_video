import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { expect, test } from 'vitest'
import HomeView from '../src/views/HomeView.vue'

test('teacher workspace keeps the existing video placeholder and visual empty state', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', name: 'home', component: HomeView }, { path: '/login', name: 'login', component: { template: '<div />' } }] })
  await router.push({ name: 'home', query: { section: 'videos' } })
  await router.isReady()
  const w = mount(HomeView, { global: { plugins: [router, ElementPlus] } })
  expect(w.text()).toContain('我的视频')
  expect(w.text()).toContain('新建视频功能即将上线')
  expect(w.find('.empty-state').exists()).toBe(true)
  expect(w.find('textarea').exists()).toBe(false)
  expect(w.find('input[type="file"]').exists()).toBe(false)
})

test('future teacher sections keep navigation context without pretending to be implemented', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', name: 'home', component: HomeView }] })
  await router.push({ name: 'home', query: { section: 'make' } })
  await router.isReady()
  const w = mount(HomeView, { global: { plugins: [router, ElementPlus] } })
  expect(w.text()).toContain('视频制作')
  expect(w.text()).toContain('视频制作功能即将上线')
})

test('account settings does not show a new video button', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', name: 'home', component: HomeView }] })
  await router.push({ name: 'home', query: { section: 'account' } })
  await router.isReady()
  const w = mount(HomeView, { global: { plugins: [router, ElementPlus] } })

  expect(w.text()).toContain('账户设置')
  expect(w.find('button[aria-label="新建视频功能即将上线"]').exists()).toBe(false)
})
