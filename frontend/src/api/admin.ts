/** 后端 /api/admin/* 接口。类型的字段名和后端 schema 保持一致。 */
import { request } from './http'

// ---------- 用户管理 ----------

export type UserRole = 'teacher' | 'admin'
export type UserStatus = 'pending' | 'active' | 'rejected' | 'disabled'
export type UserAction = 'approve' | 'reject' | 'disable' | 'enable'

export type UserOut = {
  id: string
  username: string
  role: UserRole
  status: UserStatus
  /** ISO 8601 时间 */
  created_at: string
  video_count?: number
}

export type UserList = { items: UserOut[]; total: number }

export type ListUsersParams = {
  status?: UserStatus
  q?: string
  page?: number
  page_size?: number
}

export type RegistrationSettings = { open: boolean }

export function listUsers(params: ListUsersParams = {}): Promise<UserList> {
  const query = new URLSearchParams()
  if (params.status) query.set('status', params.status)
  const q = params.q?.trim()
  if (q) query.set('q', q)
  if (params.page !== undefined) query.set('page', String(params.page))
  if (params.page_size !== undefined) query.set('page_size', String(params.page_size))
  const qs = query.toString()
  return request<UserList>('GET', `/api/admin/users${qs ? `?${qs}` : ''}`)
}

export function userAction(id: string, action: UserAction): Promise<UserOut> {
  return request<UserOut>('POST', `/api/admin/users/${encodeURIComponent(id)}/actions`, { action })
}

export function resetPassword(id: string, password: string): Promise<void> {
  return request<void>('POST', `/api/admin/users/${encodeURIComponent(id)}/password`, { password })
}

export function setRole(id: string, role: UserRole): Promise<UserOut> {
  return request<UserOut>('PUT', `/api/admin/users/${encodeURIComponent(id)}/role`, { role })
}

export function getRegistration(): Promise<RegistrationSettings> {
  return request<RegistrationSettings>('GET', '/api/admin/settings/registration')
}

export function putRegistration(open: boolean): Promise<RegistrationSettings> {
  return request<RegistrationSettings>('PUT', '/api/admin/settings/registration', { open })
}

// ---------- 页面配置 ----------

export type FieldKey =
  | 'prompt'
  | 'materials'
  | 'subject'
  | 'grade'
  | 'textbook_edition'
  | 'duration'
  | 'aspect_ratio'
  | 'voice'
  | 'web_search'

export type FieldOption = {
  value: string
  label: string
  /** 只有教材版本用：适用的科目（subject 的 option value），null 表示适用于所有科目 */
  subjects: string[] | null
}

export type FieldConfig = {
  key: FieldKey
  label: string
  visible: boolean
  default: string | boolean | null
  options: FieldOption[]
  /** 科目（subject 的 option value）→ 本项的 option value */
  default_by_subject: Record<string, string>
}

export type FormFieldsConfig = { fields: FieldConfig[] }

export type GenerationParams = {
  max_concurrent_jobs: number
  max_retries: number
  duration_tolerance_pct: number
  long_term_memory_enabled: boolean
}

export function getFormFields(): Promise<FormFieldsConfig> {
  return request<FormFieldsConfig>('GET', '/api/admin/settings/form-fields')
}

export function putFormFields(cfg: FormFieldsConfig): Promise<FormFieldsConfig> {
  return request<FormFieldsConfig>('PUT', '/api/admin/settings/form-fields', cfg)
}

export function getGenerationParams(): Promise<GenerationParams> {
  return request<GenerationParams>('GET', '/api/admin/settings/generation-params')
}

export function putGenerationParams(p: GenerationParams): Promise<GenerationParams> {
  return request<GenerationParams>('PUT', '/api/admin/settings/generation-params', p)
}

// ---------- 模型配置 ----------

export type Purpose = 'outline_llm' | 'review_llm' | 'vision_llm' | 'embedding' | 'tts' | 'web_search'

export type ApiKeyStatus = 'set' | 'missing' | 'undecryptable'

export type Voice = { speaker_id: string; label: string }

/** 后台看到的一项模型配置。API key 只有状态和掩码，没有明文。 */
export type ModelConfigView = {
  purpose: Purpose
  label: string
  required: boolean
  base_url: string
  model: string
  enabled: boolean
  api_key_status: ApiKeyStatus
  api_key_masked: string | null
  voices: Voice[]
  last_test_ok: boolean | null
  last_test_message: string | null
  last_tested_at: string | null
}

/** 修改一项配置。不改 key 时不要带 api_key；voices 只有 tts 用，不带表示保留原来的音色。 */
export type ModelConfigUpdate = {
  base_url: string
  model: string
  enabled: boolean
  api_key?: string
  clear_api_key?: boolean
  voices?: Voice[]
}

export type ProbeResult = { ok: boolean; message: string }

export function listModelConfigs(): Promise<ModelConfigView[]> {
  return request<ModelConfigView[]>('GET', '/api/admin/model-configs')
}

export function putModelConfig(purpose: Purpose, upd: ModelConfigUpdate): Promise<ModelConfigView> {
  return request<ModelConfigView>('PUT', `/api/admin/model-configs/${purpose}`, upd)
}

export function testModelConfig(purpose: Purpose): Promise<ProbeResult> {
  return request<ProbeResult>('POST', `/api/admin/model-configs/${purpose}/test`)
}
