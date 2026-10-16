import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { expect, test } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { FormFieldsConfig } from '../src/api/admin'
import AdminLayout from '../src/layouts/AdminLayout.vue'
import { addOption, cloneConfig, removeOption, setDefaultsBySubject, updateOption } from '../src/views/admin/formFieldsEdit'

// ---------- AdminLayout ----------

function makeRouter() {
  const tab = (text: string) => ({ template: `<p class="tab-body">${text}</p>` })
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/admin',
        name: 'admin',
        component: AdminLayout,
        redirect: { name: 'admin-page-config' },
        children: [
          { path: 'page-config', name: 'admin-page-config', component: tab('页面配置内容') },
          { path: 'model-config', name: 'admin-model-config', component: tab('模型配置内容') },
          { path: 'users', name: 'admin-users', component: tab('用户管理内容') },
        ],
      },
    ],
  })
}

test('admin layout: three tabs follow the child route', async () => {
  const router = makeRouter()
  await router.push('/admin')
  await router.isReady()
  const w = mount({ template: '<RouterView />' }, { global: { plugins: [router, ElementPlus] } })
  await flushPromises()

  const tabs = w.findAll('[role="tab"]')
  expect(tabs.map((t) => t.text())).toEqual(['页面配置', '模型配置', '用户管理'])
  expect(tabs[0].attributes('aria-selected')).toBe('true')
  expect(w.findAll('.tab-body').map((b) => b.text())).toEqual(['页面配置内容'])
  // 不重复 AppLayout 的 main
  expect(w.find('main').exists()).toBe(false)

  await tabs[2].trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.name).toBe('admin-users')
  expect(w.findAll('.tab-body').map((b) => b.text())).toEqual(['用户管理内容'])
  expect(w.findAll('[role="tab"]')[2].attributes('aria-selected')).toBe('true')
})

// ---------- 页面配置的编辑操作 ----------

function cfg(): FormFieldsConfig {
  const opt = (value: string, subjects: string[] | null = null) => ({ value, label: value, subjects })
  const base = { visible: true, default_by_subject: {} as Record<string, string> }
  return {
    fields: [
      { ...base, key: 'subject', label: '科目', default: '数学', options: [opt('数学'), opt('语文'), opt('历史')] },
      {
        ...base,
        key: 'textbook_edition',
        label: '教材版本',
        default: '人教版',
        options: [opt('人教版'), opt('统编版', ['语文', '历史'])],
        default_by_subject: { 语文: '统编版', 历史: '统编版' },
      },
    ],
  }
}

const field = (c: FormFieldsConfig, key: string) => c.fields.find((f) => f.key === key)!

test('renaming a subject updates edition subjects and per-subject defaults', () => {
  const c = cfg()
  updateOption(c, 'subject', 1, { value: '语文（部编）', label: '语文', subjects: null })
  expect(field(c, 'subject').options[1]).toEqual({ value: '语文（部编）', label: '语文', subjects: null })
  expect(field(c, 'textbook_edition').options[1].subjects).toEqual(['语文（部编）', '历史'])
  expect(field(c, 'textbook_edition').default_by_subject).toEqual({ '语文（部编）': '统编版', 历史: '统编版' })
})

test('renaming the default value keeps it selected', () => {
  const c = cfg()
  updateOption(c, 'textbook_edition', 0, { value: '人教版（新）', label: '人教版', subjects: [] })
  expect(field(c, 'textbook_edition').default).toBe('人教版（新）')
  // 适用科目留空 → null（所有科目）
  expect(field(c, 'textbook_edition').options[0].subjects).toBeNull()
})

test('removing options cleans up references', () => {
  const c = cfg()
  removeOption(c, 'subject', 0) // 数学是默认值
  expect(field(c, 'subject').default).toBe('语文')
  removeOption(c, 'subject', 1) // 历史
  expect(field(c, 'textbook_edition').options[1].subjects).toEqual(['语文'])
  expect(field(c, 'textbook_edition').default_by_subject).toEqual({ 语文: '统编版' })

  removeOption(c, 'textbook_edition', 1) // 统编版
  expect(field(c, 'textbook_edition').default_by_subject).toEqual({})
})

test('adding options and setting per-subject defaults', () => {
  const c = cfg()
  addOption(c, 'subject', { value: '物理', label: '物理', subjects: [] })
  expect(field(c, 'subject').options.at(-1)).toEqual({ value: '物理', label: '物理', subjects: null })
  setDefaultsBySubject(c, 'textbook_edition', { 语文: '统编版', 历史: undefined, 物理: '' })
  expect(field(c, 'textbook_edition').default_by_subject).toEqual({ 语文: '统编版' })
})

test('cloneConfig returns an independent copy', () => {
  const c = cfg()
  const copy = cloneConfig(c)
  removeOption(copy, 'subject', 0)
  expect(field(c, 'subject').options).toHaveLength(3)
})
