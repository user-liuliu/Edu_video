import { DOMWrapper, enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Component } from 'vue'
import * as api from '../src/api/admin'
import type { FieldConfig, FormFieldsConfig, GenerationParams, ModelConfigView, UserOut } from '../src/api/admin'
import { ApiError } from '../src/api/http'
import { useAuthStore } from '../src/stores/auth'
import ModelConfigTab from '../src/views/admin/ModelConfigTab.vue'
import PageConfigTab from '../src/views/admin/PageConfigTab.vue'
import UsersTab from '../src/views/admin/UsersTab.vue'

vi.mock('../src/api/admin', () => ({
  listUsers: vi.fn(),
  userAction: vi.fn(),
  resetPassword: vi.fn(),
  setRole: vi.fn(),
  getRegistration: vi.fn(),
  putRegistration: vi.fn(),
  getFormFields: vi.fn(),
  putFormFields: vi.fn(),
  getGenerationParams: vi.fn(),
  putGenerationParams: vi.fn(),
  listModelConfigs: vi.fn(),
  putModelConfig: vi.fn(),
  testModelConfig: vi.fn(),
}))

const m = vi.mocked(api)

enableAutoUnmount(afterEach)

// ---------- 测试数据 ----------

const opts = (...values: string[]) => values.map((v) => ({ value: v, label: v, subjects: null }))

function formFields(): FormFieldsConfig {
  const f = (key: FieldConfig['key'], label: string, extra: Partial<FieldConfig> = {}): FieldConfig => ({
    key,
    label,
    visible: true,
    default: null,
    options: [],
    default_by_subject: {},
    ...extra,
  })
  return {
    fields: [
      f('prompt', '想讲什么'),
      f('materials', '参考素材'),
      f('subject', '科目', { default: '数学', options: opts('数学', '语文', '历史') }),
      f('grade', '年级', { default: '初三', options: opts('初二', '初三') }),
      f('textbook_edition', '教材版本', {
        default: '人教版',
        options: [...opts('人教版', '北师大版'), { value: '统编版', label: '统编版', subjects: ['语文', '历史'] }],
        default_by_subject: { 语文: '统编版', 历史: '统编版' },
      }),
      f('duration', '视频时长', {
        default: '5',
        options: [
          { value: '3', label: '3 分钟', subjects: null },
          { value: '5', label: '5 分钟', subjects: null },
        ],
      }),
      f('aspect_ratio', '视频尺寸', { default: '16:9', options: opts('16:9', '9:16') }),
      f('voice', '配音声音'),
      f('web_search', '允许联网搜索', { default: true }),
    ],
  }
}

const params = (): GenerationParams => ({
  max_concurrent_jobs: 2,
  max_retries: 2,
  duration_tolerance_pct: 15,
  long_term_memory_enabled: true,
})

function modelCfg(purpose: ModelConfigView['purpose'], label: string, extra: Partial<ModelConfigView> = {}): ModelConfigView {
  return {
    purpose,
    label,
    required: true,
    base_url: 'https://relay.example.com/v1',
    model: 'model-x',
    enabled: true,
    api_key_status: 'set',
    api_key_masked: 'sk-****8f2a',
    voices: [],
    last_test_ok: true,
    last_test_message: '连接正常',
    last_tested_at: '2026-10-16T08:00:00Z',
    ...extra,
  }
}

function modelConfigs(): ModelConfigView[] {
  return [
    modelCfg('outline_llm', '写大纲/讲稿'),
    modelCfg('review_llm', '审核', { api_key_status: 'undecryptable', api_key_masked: null, last_test_ok: null }),
    modelCfg('vision_llm', '看图识别', { last_test_ok: false, last_test_message: '接口返回 401' }),

    modelCfg('embedding', 'Embedding', { required: false, enabled: false }),
    modelCfg('tts', '配音', { voices: [{ speaker_id: 'zh_female_1', label: '温和女声' }] }),
    modelCfg('web_search', '联网搜索', {
      required: false,
      enabled: false,
      base_url: '',
      model: '',
      api_key_status: 'missing',
      api_key_masked: null,
      last_test_ok: null,
      last_test_message: null,
      last_tested_at: null,
    }),
  ]
}

const user = (id: string, username: string, status: UserOut['status'], role: UserOut['role'] = 'teacher'): UserOut => ({
  id,
  username,
  role,
  status,
  created_at: '2026-10-16T08:30:00Z',
})

const users = (): UserOut[] => [
  user('u1', '张老师', 'pending'),
  user('u2', '李老师', 'active'),
  user('u3', '赵老师', 'disabled'),
  user('u4', '钱老师', 'rejected'),
  user('u5', 'admin', 'active', 'admin'),
]

// ---------- 工具函数 ----------

let messageError: ReturnType<typeof vi.fn>
let messageSuccess: ReturnType<typeof vi.fn>
let confirm: ReturnType<typeof vi.fn>
let pinia: Pinia

beforeEach(() => {
  vi.resetAllMocks()
  pinia = createPinia()
  setActivePinia(pinia)
  // 当前登录的管理员是另一个账号（不是列表里的任何人）
  useAuthStore().user = { id: 'me', username: '我', role: 'admin', status: 'active' }
  m.listUsers.mockResolvedValue({ items: users(), total: 5 })
  m.getRegistration.mockResolvedValue({ open: true })
  m.getFormFields.mockResolvedValue(formFields())
  m.getGenerationParams.mockResolvedValue(params())
  m.listModelConfigs.mockResolvedValue(modelConfigs())
  messageError = vi.fn()
  messageSuccess = vi.fn()
  vi.spyOn(ElMessage, 'error').mockImplementation(messageError as never)
  vi.spyOn(ElMessage, 'success').mockImplementation(messageSuccess as never)
  confirm = vi.fn().mockResolvedValue('confirm')
  vi.spyOn(ElMessageBox, 'confirm').mockImplementation(confirm as never)
})

async function mountTab(c: Component): Promise<VueWrapper> {
  const w = mount(c, { global: { plugins: [pinia, ElementPlus] }, attachTo: document.body })
  await flushPromises()
  return w
}

test('page configuration omits legacy explanation style and does not submit it again', async () => {
  const legacy=formFields()
  legacy.fields.push({key:'style',label:'讲解风格',visible:true,default:'auto',options:[],default_by_subject:{}} as unknown as FieldConfig)
  m.getFormFields.mockResolvedValue(legacy)
  const w=await mountTab(PageConfigTab)
  expect(w.text()).not.toContain('讲解风格')
  expect(w.text()).toContain('配音声音')
  m.putFormFields.mockImplementation(async cfg=>cfg)
  const save=w.findAll('button').find(b=>b.text()==='保存')
  expect(save).toBeDefined()
  await save!.trigger('click');await flushPromises()
  expect(m.putFormFields).toHaveBeenCalled()
  expect(m.putFormFields.mock.calls[0]![0].fields.some((f: {key:string})=>f.key==='style')).toBe(false)
  w.unmount()
})

type Scope = VueWrapper | DOMWrapper<Element>

/** 按行首单元格（行标题）的文字找到表格行 */
function row(w: Scope, name: string) {
  const r = w.findAll('tbody tr').find((tr) => tr.find('th').text().includes(name))
  if (!r) throw new Error(`没有找到「${name}」这一行`)
  return r
}

function buttons(w: Scope) {
  return w.findAll('button').map((b) => b.text()).filter(Boolean)
}

function button(w: Scope, text: string) {
  const b = w.findAll('button').find((x) => x.text() === text)
  if (!b) throw new Error(`没有找到按钮「${text}」`)
  return b
}

function section(w: Scope, title: string) {
  const s = w.findAll('section').find((x) => x.find('h2, h3').exists() && x.find('h2, h3').text() === title)
  if (!s) throw new Error(`没有找到「${title}」部分`)
  return s
}

/** 按可见的标签文字找到表单项里的输入框，并确认标签和输入框关联 */
function field(w: Scope, label: string) {
  const item = w.findAll('.el-form-item').find((i) => i.find('label').text() === label)
  if (!item) throw new Error(`没有找到标签为「${label}」的输入框`)
  const input = item.find('input')
  expect(item.find('label').attributes('for')).toBe(input.attributes('id'))
  return input
}

// ---------- 用户管理 ----------

test('users: action buttons by status', async () => {
  const w = await mountTab(UsersTab)
  expect(m.listUsers).toHaveBeenCalledWith({ page: 1, page_size: 20 })
  expect(w.findAll('thead th').map((th) => th.text())).toEqual(['用户名', '角色', '状态', '注册时间', '视频项目数', '操作'])

  expect(buttons(row(w, '张老师'))).toEqual(['通过', '拒绝'])
  expect(row(w, '张老师').text()).toContain('待审核')
  expect(buttons(row(w, '李老师'))).toEqual(['停用', '重置密码', '设为管理员'])
  expect(row(w, '李老师').text()).toContain('老师')
  expect(buttons(row(w, '赵老师'))).toEqual(['启用', '重置密码'])
  expect(buttons(row(w, '钱老师'))).toEqual(['通过'])
  expect(buttons(row(w, 'admin'))).toEqual(['停用', '重置密码', '取消管理员'])
  expect(row(w, 'admin').text()).toContain('管理员')
  // 注册时间按本地时间显示
  expect(row(w, '张老师').text()).toContain(new Date('2026-10-16T08:30:00Z').toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }))
})

test('users: last_admin error surfaces server message', async () => {
  m.userAction.mockRejectedValue(new ApiError(409, 'last_admin', '系统至少需要保留一个管理员'))
  m.setRole.mockRejectedValue(new ApiError(409, 'last_admin', '系统至少需要保留一个管理员'))
  const w = await mountTab(UsersTab)

  await button(row(w, 'admin'), '停用').trigger('click')
  await flushPromises()
  expect(confirm).toHaveBeenCalledTimes(1)
  expect(m.userAction).toHaveBeenCalledWith('u5', 'disable')
  expect(messageError).toHaveBeenCalledWith('系统至少需要保留一个管理员')

  await button(row(w, 'admin'), '取消管理员').trigger('click')
  await flushPromises()
  expect(confirm).toHaveBeenCalledTimes(2)
  expect(m.setRole).toHaveBeenCalledWith('u5', 'teacher')
  expect(messageError).toHaveBeenCalledTimes(2)
  expect(messageError).toHaveBeenLastCalledWith('系统至少需要保留一个管理员')
})

const SELF_NOTE = '这是你自己的账号，操作后你需要重新登录'

test('users: actions on your own account warn in the confirmation', async () => {
  useAuthStore().user = { id: 'u5', username: 'admin', role: 'admin', status: 'active' }
  confirm.mockRejectedValue('cancel')
  const w = await mountTab(UsersTab)

  await button(row(w, 'admin'), '停用').trigger('click')
  await flushPromises()
  expect(confirm.mock.calls[0][0]).toContain(SELF_NOTE)

  await button(row(w, 'admin'), '取消管理员').trigger('click')
  await flushPromises()
  expect(confirm.mock.calls[1][0]).toContain('这是你自己的账号')
  expect(confirm.mock.calls[1][0]).toContain('你将失去管理后台权限')
  expect(m.userAction).not.toHaveBeenCalled()
  expect(m.setRole).not.toHaveBeenCalled()

  await button(row(w, 'admin'), '重置密码').trigger('click')
  await flushPromises()
  const dialog = w.findAll('.el-dialog').find((d) => d.isVisible() && d.text().includes('重置密码'))!
  expect(dialog.text()).toContain(SELF_NOTE)
})

test('users: actions on other accounts have no self warning', async () => {
  confirm.mockRejectedValue('cancel')
  const w = await mountTab(UsersTab)
  await button(row(w, 'admin'), '停用').trigger('click')
  await flushPromises()
  await button(row(w, 'admin'), '取消管理员').trigger('click')
  await flushPromises()
  for (const [text] of confirm.mock.calls) expect(text).not.toContain('这是你自己的账号')

  await button(row(w, '李老师'), '重置密码').trigger('click')
  await flushPromises()
  const dialog = w.findAll('.el-dialog').find((d) => d.isVisible() && d.text().includes('重置密码'))!
  expect(dialog.text()).not.toContain('这是你自己的账号')
})

test('users: cancelling the confirm dialog does nothing', async () => {
  confirm.mockRejectedValue('cancel')
  const w = await mountTab(UsersTab)
  await button(row(w, '张老师'), '拒绝').trigger('click')
  await flushPromises()
  expect(confirm).toHaveBeenCalled()
  expect(m.userAction).not.toHaveBeenCalled()
  expect(messageError).not.toHaveBeenCalled()
})

test('users: approve calls the API and reloads the list', async () => {
  m.userAction.mockResolvedValue({ ...user('u1', '张老师', 'active') })
  const w = await mountTab(UsersTab)
  await button(row(w, '张老师'), '通过').trigger('click')
  await flushPromises()
  // 通过不需要确认
  expect(confirm).not.toHaveBeenCalled()
  expect(m.userAction).toHaveBeenCalledWith('u1', 'approve')
  expect(messageSuccess).toHaveBeenCalled()
  expect(m.listUsers).toHaveBeenCalledTimes(2)
})

test('users: reset password requires matching passwords', async () => {
  m.resetPassword.mockResolvedValue(undefined)
  const w = await mountTab(UsersTab)
  await button(row(w, '李老师'), '重置密码').trigger('click')
  await flushPromises()
  const dialog = w.find('.el-dialog')
  expect(dialog.text()).toContain('重置密码：李老师')

  await field(dialog, '新密码').setValue('newpass123')
  await field(dialog, '确认新密码').setValue('newpass124')
  await button(dialog, '确定').trigger('click')
  await flushPromises()
  await vi.waitFor(() => expect(dialog.text()).toContain('两次输入的密码不一致'))
  expect(m.resetPassword).not.toHaveBeenCalled()

  await field(dialog, '确认新密码').setValue('newpass123')
  await button(dialog, '确定').trigger('click')
  await flushPromises()
  expect(m.resetPassword).toHaveBeenCalledWith('u2', 'newpass123')
  expect(messageSuccess).toHaveBeenCalled()
})

test('users: registration switch saves the new value', async () => {
  m.putRegistration.mockResolvedValue({ open: false })
  const w = await mountTab(UsersTab)
  const sw = w.find('[role="switch"][aria-label="开放注册"]')
  expect(sw.attributes('aria-checked')).toBe('true')
  await w.find('.registration .el-switch').trigger('click')
  await flushPromises()
  expect(m.putRegistration).toHaveBeenCalledWith(false)
})

// ---------- 页面配置 ----------

test('page config: prompt visible switch is disabled', async () => {
  const w = await mountTab(PageConfigTab)
  const prompt = row(w, '想讲什么')
  expect(prompt.find('.el-switch').classes()).toContain('is-disabled')
  expect(prompt.find('[role="switch"]').attributes('disabled')).toBeDefined()
  expect(prompt.text()).toContain('必填，不能隐藏')
  // 其他行的开关可以改
  expect(row(w, '科目').find('.el-switch').classes()).not.toContain('is-disabled')
  // 音色在模型配置里维护，这一行不能编辑可选值
  expect(row(w, '配音声音').text()).toContain('音色在模型配置中维护')
  expect(buttons(row(w, '配音声音'))).toEqual([])
  // 联网搜索的默认值是开关
  expect(row(w, '允许联网搜索').findAll('[role="switch"]')).toHaveLength(2)
})

test('page config: save error shows server message', async () => {
  m.putFormFields.mockRejectedValue(
    new ApiError(422, 'validation_error', 'Value error, 默认值必须在可选值中：subject 的默认值不在可选值里'),
  )
  const w = await mountTab(PageConfigTab)
  await button(section(w, '新建视频页面选项'), '保存').trigger('click')
  await flushPromises()
  expect(m.putFormFields).toHaveBeenCalledWith(formFields())
  expect(messageError).toHaveBeenCalledWith('默认值必须在可选值中：subject 的默认值不在可选值里')
  expect(messageSuccess).not.toHaveBeenCalled()
})

test('page config: option chips are shown and editable', async () => {
  const w = await mountTab(PageConfigTab)
  const edition = row(w, '教材版本')
  expect(buttons(edition)).toEqual(['人教版', '北师大版', '统编版', '+ 添加', '各科目默认版本'])
  expect(edition.text()).toContain('语文、历史')

  await button(row(w, '科目'), '+ 添加').trigger('click')
  await flushPromises()
  const dialog = w.findAll('.el-dialog').find((d) => d.isVisible() && d.text().includes('添加可选值'))!
  await field(dialog, '值').setValue('物理')
  await field(dialog, '显示名称').setValue('物理')
  await button(dialog, '确定').trigger('click')
  await flushPromises()
  expect(buttons(row(w, '科目'))).toEqual(['数学', '语文', '历史', '物理', '+ 添加'])

  m.putFormFields.mockImplementation(async (cfg) => cfg)
  await button(section(w, '新建视频页面选项'), '保存').trigger('click')
  await flushPromises()
  const sent = m.putFormFields.mock.calls[0][0]
  expect(sent.fields.find((f) => f.key === 'subject')!.options.at(-1)).toEqual({ value: '物理', label: '物理', subjects: null })
  expect(messageSuccess).toHaveBeenCalledWith('已保存')
})

test('page config: generation params save', async () => {
  m.putGenerationParams.mockImplementation(async (p) => p)
  const w = await mountTab(PageConfigTab)
  const s = section(w, '生成参数')
  expect(s.text()).not.toContain('每段画面数')
  expect(s.text()).not.toContain('每分钟插图上限')
  expect(field(s, '同时生成的任务数').attributes('aria-valuemin')).toBe('1')
  expect(field(s, '同时生成的任务数').attributes('aria-valuemax')).toBe('20')
  expect(field(s, '失败重试次数').attributes('aria-valuemax')).toBe('5')
  expect(s.find('[role="switch"][aria-label="长期记忆"]').exists()).toBe(true)
  await button(s, '保存').trigger('click')
  await flushPromises()
  expect(m.putGenerationParams).toHaveBeenCalledWith(params())
  expect(messageSuccess).toHaveBeenCalledWith('已保存')
})

// ---------- 模型配置 ----------

test('model config: undecryptable shows warning text', async () => {
  const w = await mountTab(ModelConfigTab)
  expect(w.findAll('tbody tr')).toHaveLength(6)
  expect(w.findAll('thead th').map((th) => th.text())).toEqual(['用途', '接口地址', 'Key', '模型', '状态', '操作'])
  const bad = row(w, '审核').find('.key-undecryptable')
  expect(bad.text()).toBe('无法解密，请重新填写')
  expect(row(w, '写大纲/讲稿').text()).toContain('sk-****8f2a')
  expect(row(w, '联网搜索').text()).toContain('未设置')
  // 状态列
  expect(row(w, '写大纲/讲稿').text()).toContain('正常')
  expect(row(w, '审核').text()).toContain('未测试')
  expect(row(w, '看图识别').text()).toContain('失败')
  expect(row(w, 'Embedding').text()).toContain('未启用')
  // 必需项有问题：顶部警告
  expect(w.find('.el-alert').text()).toContain('老师暂时无法新建视频')
})

test('model config: no warning when every required item is usable', async () => {
  m.listModelConfigs.mockResolvedValue(
    modelConfigs().map((c) => (c.required ? { ...c, api_key_status: 'set', api_key_masked: 'sk-****1111', last_test_ok: true } : c)),
  )
  const w = await mountTab(ModelConfigTab)
  expect(w.text()).not.toContain('老师暂时无法新建视频')
})

test('model config: empty key input omits api_key in payload', async () => {
  m.putModelConfig.mockImplementation(async (purpose) => modelConfigs().find((c) => c.purpose === purpose)!)
  const w = await mountTab(ModelConfigTab)
  await button(row(w, '写大纲/讲稿'), '编辑').trigger('click')
  await flushPromises()
  const dialog = w.find('.el-dialog')
  expect(dialog.text()).toContain('编辑模型配置：写大纲/讲稿')
  expect(field(dialog, '接口地址').attributes('placeholder')).toBe('例如 https://example.com/v1')
  const key = field(dialog, 'API Key')
  expect(key.attributes('type')).toBe('password')
  expect(key.attributes('placeholder')).toBe('留空表示不修改')
  expect((key.element as HTMLInputElement).value).toBe('')
  expect(dialog.text()).toContain('清除已保存的 Key')
  // tts 以外没有音色编辑器
  expect(dialog.text()).not.toContain('音色 ID')

  await field(dialog, '模型名称').setValue('model-y')
  await button(dialog, '保存').trigger('click')
  await flushPromises()
  expect(m.putModelConfig).toHaveBeenCalledTimes(1)
  const [purpose, upd] = m.putModelConfig.mock.calls[0]
  expect(purpose).toBe('outline_llm')
  expect(upd).toEqual({ base_url: 'https://relay.example.com/v1', model: 'model-y', enabled: true })
  expect('api_key' in upd).toBe(false)
  expect('voices' in upd).toBe(false)
  expect(messageSuccess).toHaveBeenCalledWith('已保存')
})

test('model config: tts dialog edits voices and sends a new key', async () => {
  m.putModelConfig.mockImplementation(async (purpose) => modelConfigs().find((c) => c.purpose === purpose)!)
  const w = await mountTab(ModelConfigTab)
  await button(row(w, '配音'), '编辑').trigger('click')
  await flushPromises()
  const dialog = w.find('.el-dialog')
  expect(field(dialog, '接口地址').attributes('placeholder')).toBe('https://openspeech.bytedance.com')
  expect(dialog.find('input[aria-label="音色 ID 1"]').element).toHaveProperty('value', 'zh_female_1')
  expect(dialog.find('input[aria-label="显示名称 1"]').element).toHaveProperty('value', '温和女声')
  await button(dialog, '添加音色').trigger('click')
  await dialog.find('input[aria-label="音色 ID 2"]').setValue('zh_male_1')
  await dialog.find('input[aria-label="显示名称 2"]').setValue('沉稳男声')
  await field(dialog, 'API Key').setValue('  new-secret-key  ')
  await button(dialog, '保存').trigger('click')
  await flushPromises()
  expect(m.putModelConfig).toHaveBeenCalledWith('tts', {
    base_url: 'https://relay.example.com/v1',
    model: 'model-x',
    enabled: true,
    api_key: 'new-secret-key',
    voices: [
      { speaker_id: 'zh_female_1', label: '温和女声' },
      { speaker_id: 'zh_male_1', label: '沉稳男声' },
    ],
  })
})

test('model config: web_search can test the configured Tavily service', async () => {
  m.testModelConfig.mockResolvedValue({ ok: true, message: '连接正常' })
  const w = await mountTab(ModelConfigTab)
  const ws = row(w, '联网搜索')
  expect(button(ws, '测试').attributes('disabled')).toBeUndefined()
  await button(ws, '测试').trigger('click')
  await flushPromises()
  expect(m.testModelConfig).toHaveBeenCalledWith('web_search')

  // 其他用途可以测试，结果用 message 显示
  await button(row(w, '写大纲/讲稿'), '测试').trigger('click')
  await flushPromises()
  expect(m.testModelConfig).toHaveBeenCalledWith('outline_llm')
  expect(messageSuccess).toHaveBeenCalledWith('连接正常')
  expect(m.listModelConfigs).toHaveBeenCalledTimes(3)
})
